"""Frontend Streamlit para el agente de desarrollo dirigido por specs.

Ejecutar en local:
    streamlit run app.py

En Cloud Run el CMD del contenedor lanza esto en $PORT.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import os
from pathlib import Path

import streamlit as st

from src.config import (
    APP_PASSWORD,
    MAX_REQUIREMENTS_CHARS,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
)
from src.cost import global_tracker
from src.graph import build_graph
from src.rate_limit import check_rate_limit
from src.state import SpecState

st.set_page_config(
    page_title="Agente de Desarrollo Dirigido por Specs",
    page_icon="📋",
    layout="wide",
)


def _gate_auth() -> bool:
    """Pide password si APP_PASSWORD está configurado. Devuelve True si autenticado."""
    if not APP_PASSWORD:
        return True  # modo dev local sin auth

    if st.session_state.get("autenticado"):
        return True

    st.markdown("### 🔐 Acceso restringido")
    st.caption(
        "Esta aplicación está protegida con un password compartido. "
        "Pídelo al administrador."
    )
    with st.form("auth_form", clear_on_submit=False):
        password = st.text_input("Password", type="password")
        entrar = st.form_submit_button("Entrar", type="primary")

    if entrar:
        # compare_digest evita timing attacks (no es crítico aquí pero es la
        # forma correcta de comparar secretos en Python).
        if hmac.compare_digest(password, APP_PASSWORD):
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Password incorrecto.")
    return False

def _mostrar_error_amigable(exc: Exception) -> None:
    """Traduce errores comunes de Anthropic a mensajes claros para el usuario."""
    from anthropic import AuthenticationError, BadRequestError, RateLimitError

    mensaje = str(exc)

    if isinstance(exc, BadRequestError) and "credit balance" in mensaje.lower():
        st.error(
            "💳 **Se acabaron los créditos de la API de Anthropic.**\n\n"
            "Recarga en [console.anthropic.com/settings/billing]"
            "(https://console.anthropic.com/settings/billing) "
            "y vuelve a intentarlo. No hace falta redesplegar."
        )
        return

    if isinstance(exc, AuthenticationError):
        st.error(
            "🔑 **Clave de API inválida o revocada.**\n\n"
            "Verifica `ANTHROPIC_API_KEY` en tu `.env` (local) o en "
            "Secret Manager (Cloud Run). La clave debe empezar por `sk-ant-` "
            "y estar activa en [console.anthropic.com/settings/keys]"
            "(https://console.anthropic.com/settings/keys)."
        )
        return

    if isinstance(exc, RateLimitError):
        st.error(
            "⏱️ **Límite de peticiones de Anthropic alcanzado.**\n\n"
            "Espera unos segundos y vuelve a intentarlo. Si pasa a menudo, "
            "considera subir el rate limit en tu cuenta o reducir el tamaño "
            "de los requisitos."
        )
        return

    if isinstance(exc, BadRequestError):
        st.error(f"❌ **Petición rechazada por Anthropic:** {mensaje}")
        return

    # Fallback: traceback completo para errores no esperados.
    st.error("❌ Error inesperado en el pipeline:")
    st.exception(exc)


def _comprobar_api_key() -> bool:
    if os.getenv("ANTHROPIC_API_KEY"):
        return True
    st.error(
        "`ANTHROPIC_API_KEY` no está configurada. Defínela como variable de "
        "entorno (en local en `.env`, en Cloud Run como secreto) antes de ejecutar."
    )
    return False


def _client_ip() -> str:
    """Obtiene la IP del cliente desde los headers que pone Cloud Run.

    En local devuelve 'local'. Cae a 'unknown' si no hay header — eso
    significa que todos comparten la misma cuota, lo cual es la opción
    segura por defecto.
    """
    try:
        headers = st.context.headers  # disponible en Streamlit >= 1.37
    except Exception:  # noqa: BLE001
        return "local"
    # Cloud Run/GCLB pone la IP real como primer valor de X-Forwarded-For.
    fwd = headers.get("X-Forwarded-For") if headers else None
    if fwd:
        return fwd.split(",")[0].strip()
    return headers.get("X-Real-IP", "unknown") if headers else "unknown"


def _comprobar_rate_limit() -> bool:
    """True si el cliente puede continuar; False si está rate-limited."""
    ip = _client_ip()
    permitido, esperar = check_rate_limit(
        key=ip,
        max_requests=RATE_LIMIT_REQUESTS,
        window_seconds=RATE_LIMIT_WINDOW_SECONDS,
    )
    if not permitido:
        st.error(
            f"⏱️ Has hecho demasiadas peticiones. Espera **{esperar} segundos** "
            f"antes de volver a intentarlo. "
            f"(Límite: {RATE_LIMIT_REQUESTS} peticiones por "
            f"{RATE_LIMIT_WINDOW_SECONDS}s.)"
        )
        return False
    return True


def _comprobar_longitud_input(texto: str) -> bool:
    """Rechaza inputs absurdamente largos para evitar facturas inesperadas."""
    if len(texto) > MAX_REQUIREMENTS_CHARS:
        st.error(
            f"📏 El texto introducido tiene {len(texto):,} caracteres y supera "
            f"el límite de {MAX_REQUIREMENTS_CHARS:,}. "
            "Resume los requisitos en una versión más corta."
        )
        return False
    return True


def _ejecutar_pipeline(requisitos: str) -> tuple[dict, dict]:
    """Ejecuta el grafo y devuelve (resultado, coste_de_esta_ejecucion)."""
    tracker = global_tracker()
    tokens_in_antes = tracker.total_tokens_in
    tokens_out_antes = tracker.total_tokens_out
    usd_antes = tracker.total_usd

    graph = build_graph()
    initial = SpecState(raw_requirements=requisitos)
    resultado = asyncio.run(graph.ainvoke(initial))

    coste_ejecucion = {
        "tokens_in": tracker.total_tokens_in - tokens_in_antes,
        "tokens_out": tracker.total_tokens_out - tokens_out_antes,
        "usd": tracker.total_usd - usd_antes,
    }
    return resultado, coste_ejecucion


def _render_estructurados(sr: dict) -> None:
    st.subheader("Requisitos extraídos")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Dominio:** {sr.get('domain', '_desconocido_')}")
        st.markdown("**Entidades**")
        st.write(sr.get("entities") or "_ninguna_")
        st.markdown("**Acciones**")
        st.write(sr.get("actions") or "_ninguna_")
    with col2:
        st.markdown("**Restricciones**")
        st.write(sr.get("constraints") or "_ninguna_")
        st.markdown("**Integraciones**")
        st.write(sr.get("integrations") or "_ninguna_")
        st.markdown("**Resumen**")
        st.info(sr.get("raw_summary", ""))


def _render_validacion(resultados: list) -> None:
    st.subheader("Resultados de validación")
    if not resultados:
        st.warning("No se registraron resultados de validación.")
        return
    for r in resultados:
        # Acepta ValidationResult (Pydantic) o dict — los nodos LangGraph pueden
        # devolver cualquiera dependiendo de la versión.
        if isinstance(r, dict):
            is_valid = r.get("is_valid", False)
            spec_type = r.get("spec_type", "")
            issues = r.get("issues", []) or []
            suggestions = r.get("suggestions", []) or []
        else:
            is_valid = getattr(r, "is_valid", False)
            spec_type = getattr(r, "spec_type", "")
            issues = getattr(r, "issues", []) or []
            suggestions = getattr(r, "suggestions", []) or []
        icono = "✅" if is_valid else "❌"
        with st.expander(f"{icono} `{spec_type}`", expanded=not is_valid):
            if issues:
                st.markdown("**Problemas**")
                for i in issues:
                    st.markdown(f"- {i}")
            if suggestions:
                st.markdown("**Sugerencias**")
                for s in suggestions:
                    st.markdown(f"- {s}")
            if is_valid and not issues:
                st.success("Todas las comprobaciones pasaron.")


def _render_artefactos(output_path: str) -> None:
    st.subheader("Artefactos generados")
    out = Path(output_path)
    if not out.exists():
        st.warning(f"Ruta de salida no encontrada: {output_path}")
        return

    archivos = sorted(p for p in out.rglob("*") if p.is_file())
    if not archivos:
        st.info("No se escribió ningún archivo.")
        return

    tabs = st.tabs([str(p.relative_to(out)) for p in archivos])
    for tab, path in zip(tabs, archivos):
        with tab:
            contenido = path.read_text(encoding="utf-8", errors="replace")
            suffix = path.suffix.lower()
            lenguaje = {
                ".yaml": "yaml",
                ".yml": "yaml",
                ".json": "json",
                ".md": "markdown",
                ".feature": "gherkin",
            }.get(suffix, "text")
            if suffix == ".md":
                st.markdown(contenido)
            else:
                st.code(contenido, language=lenguaje)
            st.download_button(
                "Descargar",
                data=contenido.encode("utf-8"),
                file_name=path.name,
                mime="text/plain",
                key=f"dl-{path}",
            )


def main() -> None:
    if not _gate_auth():
        return

    st.title("📋 Agente de Desarrollo Dirigido por Specs")
    st.caption(
        "Convierte requisitos en lenguaje natural en specs OpenAPI, Gherkin "
        "y de agente — en paralelo."
    )

    with st.sidebar:
        if APP_PASSWORD and st.button("Cerrar sesión"):
            st.session_state.pop("autenticado", None)
            st.rerun()

        # Coste acumulado en este contenedor (vida del proceso).
        tracker = global_tracker()
        if tracker.entries:
            st.subheader("💰 Coste acumulado")
            st.metric(
                "Total",
                f"${tracker.total_usd:.4f}",
                help="Coste estimado en USD desde que arrancó el contenedor "
                "(no se persiste tras reinicios).",
            )
            st.caption(
                f"{len(tracker.entries)} llamadas · "
                f"{tracker.total_tokens_in:,} in · {tracker.total_tokens_out:,} out"
            )
            st.divider()

        st.header("Ajustes")
        st.text_input(
            "Modelo de generación",
            value=os.getenv("GENERATION_MODEL", "claude-opus-4-7"),
            disabled=True,
            help="Configurable mediante la variable de entorno GENERATION_MODEL.",
        )
        st.text_input(
            "Modelo utilitario",
            value=os.getenv("UTILITY_MODEL", "claude-haiku-4-5-20251001"),
            disabled=True,
            help="Configurable mediante la variable de entorno UTILITY_MODEL.",
        )
        st.text_input(
            "Directorio de salida",
            value=os.getenv("OUTPUT_DIR", "./output"),
            disabled=True,
            help="En Cloud Run debe ser /tmp/output (tmpfs con permiso de escritura).",
        )
        st.divider()
        st.markdown(
            "**Pipeline**: analizar → enrutar → "
            "(openapi ∥ gherkin ∥ agente) → validar → consolidar"
        )

    requisitos = st.text_area(
        "Describe tu sistema en lenguaje natural",
        height=220,
        placeholder="p. ej. Construir una API REST para gestionar suscripciones con Stripe…",
        key="requisitos",
    )

    # Dos botones lado a lado: "Generar" siempre visible; "Limpiar" solo si hay
    # un resultado guardado de una ejecución anterior.
    col_a, col_b = st.columns([3, 1])
    pulsado = col_a.button("Generar specs", type="primary", use_container_width=True)
    hay_resultado_previo = st.session_state.get("ultimo_resultado") is not None
    if hay_resultado_previo:
        if col_b.button("Limpiar", use_container_width=True):
            st.session_state.pop("ultimo_resultado", None)
            st.rerun()

    if pulsado:
        if not requisitos.strip():
            st.warning("Escribe primero los requisitos del sistema.")
        elif not _comprobar_longitud_input(requisitos):
            pass
        elif not _comprobar_rate_limit():
            pass
        elif not _comprobar_api_key():
            pass
        else:
            with st.status(
                "Ejecutando pipeline de generación de specs…", expanded=True
            ) as status:
                try:
                    st.write(
                        "⏳ Analizando requisitos, enrutando, generando, validando…"
                    )
                    resultado, _ = _ejecutar_pipeline(requisitos.strip())
                    status.update(label="Pipeline completado", state="complete")
                    # Persistir el resultado en session_state. Es lo que evita que
                    # un rerun (provocado p. ej. por st.download_button) borre la
                    # vista. El render se hace siempre desde session_state.
                    st.session_state["ultimo_resultado"] = resultado
                except Exception as exc:  # noqa: BLE001
                    status.update(label="Pipeline fallido", state="error")
                    _mostrar_error_amigable(exc)

    # Render desde session_state — sobrevive a cualquier interacción posterior
    # (descargas, expanders, cambio de pestaña…) sin re-ejecutar el pipeline.
    resultado = st.session_state.get("ultimo_resultado")
    if resultado is not None:
        _render_resultado(resultado)


def _render_resultado(resultado: dict) -> None:
    """Renderiza un resultado de pipeline previamente almacenado."""
    resumen = resultado.get("final_summary")
    if resumen:
        st.success(resumen)

    sr = resultado.get("structured_requirements")
    if sr is not None:
        _render_estructurados(
            sr.model_dump() if hasattr(sr, "model_dump") else sr
        )

    _render_validacion(resultado.get("validation_results", []))

    output_path = resultado.get("output_path")
    if output_path:
        st.code(output_path, language="text")
        _render_artefactos(output_path)


if __name__ == "__main__":
    main()

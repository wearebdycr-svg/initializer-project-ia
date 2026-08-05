import streamlit as st
import os
import sys
import importlib

# Forzar la recarga del módulo solo si ya fue importado previamente para evitar el caché de Streamlit sin fallar al inicio
if 'agent_project_initializer' in sys.modules:
    importlib.reload(sys.modules['agent_project_initializer'])

from agent_project_initializer import (
    DOCUMENTS_DIR,
    validate_mandatory_answer,
    normalize_project_type,
    resolve_stack_choice,
    resolve_destination_path,
    check_missing_binaries,
    create_project_structure,
    install_dependencies,
    create_executors,
)

# Configuración de la página
st.set_page_config(
    page_title="Agente Inicializador de Proyectos",
    page_icon="🛠️",
    layout="centered"
)

st.title("Agente Inicializador de Proyectos 🛠️")
st.markdown(
    """
    **¡Bienvenido al asistente de inicialización de proyectos!**
    Te guiaré por una fase de descubrimiento (tipo de proyecto y stack), confirmaremos la ruta de destino
    dentro de `~/Documents` y, antes de instalar cualquier dependencia, te pediré aprobación explícita
    (**Human-in-the-loop**).
    """
)

WELCOME_MESSAGE = (
    "¡Hola! Soy tu asistente para inicializar proyectos de software. 🚀\n\n"
    "Para empezar, cuéntame: **¿qué tipo de proyecto deseas iniciar? (Web / Mobile)**"
)

# Inicializar estados de IA si no existen
if "provider" not in st.session_state:
    st.session_state.provider = "Google Gemini"

if "api_key" not in st.session_state:
    st.session_state.api_key = ""

if "model_name" not in st.session_state:
    try:
        from agent_project_initializer import default_model
    except Exception:
        default_model = "gemini-3.1-flash-lite"
    st.session_state.model_name = default_model

# Función para auto-inicializar usando variables de entorno si están disponibles y no se ha configurado antes
if "stack_advisor_executor" not in st.session_state or st.session_state.stack_advisor_executor is None:
    # Intentar auto-inicializar si las claves de entorno están presentes
    google_key = os.environ.get("GOOGLE_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    
    initialized = False
    if google_key and st.session_state.provider == "Google Gemini":
        try:
            st.session_state.stack_advisor_executor, st.session_state.plan_summary_executor = create_executors(
                "Google Gemini", google_key, st.session_state.model_name
            )
            st.session_state.api_key = google_key
            initialized = True
        except Exception:
            pass
    elif openai_key and st.session_state.provider == "OpenAI":
        try:
            st.session_state.stack_advisor_executor, st.session_state.plan_summary_executor = create_executors(
                "OpenAI", openai_key, st.session_state.model_name
            )
            st.session_state.api_key = openai_key
            initialized = True
        except Exception:
            pass
    elif anthropic_key and st.session_state.provider == "Anthropic Claude":
        try:
            st.session_state.stack_advisor_executor, st.session_state.plan_summary_executor = create_executors(
                "Anthropic Claude", anthropic_key, st.session_state.model_name
            )
            st.session_state.api_key = anthropic_key
            initialized = True
        except Exception:
            pass
            
    if not initialized:
        st.session_state.stack_advisor_executor = None
        st.session_state.plan_summary_executor = None

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": WELCOME_MESSAGE}]

if "chat_step" not in st.session_state:
    st.session_state.chat_step = "type"  # Choices: "type", "stack", "path", "review", "done"

if "project_type" not in st.session_state:
    st.session_state.project_type = None

if "stack" not in st.session_state:
    st.session_state.stack = None

if "destination_path" not in st.session_state:
    st.session_state.destination_path = None


def reset_conversation():
    st.session_state.messages = [{"role": "assistant", "content": WELCOME_MESSAGE}]
    st.session_state.chat_step = "type"
    st.session_state.project_type = None
    st.session_state.stack = None
    st.session_state.destination_path = None


# Menú lateral
with st.sidebar:
    st.image("https://img.icons8.com/?size=100&id=103790&format=png&color=000000", width=100)
    st.subheader("Configuración & Control")
    
    # Sección de Configuración de IA
    st.markdown("---")
    st.markdown("### 🔑 Configuración de IA")
    
    # Selector de proveedor
    provider_options = ["Google Gemini", "OpenAI", "Anthropic Claude"]
    selected_provider = st.selectbox(
        "Proveedor de IA", 
        options=provider_options, 
        index=provider_options.index(st.session_state.provider)
    )
    
    # Si cambia el proveedor, actualizamos el modelo por defecto en el campo de texto y recargamos
    if selected_provider != st.session_state.provider:
        st.session_state.provider = selected_provider
        if selected_provider == "Google Gemini":
            try:
                from agent_project_initializer import default_model
            except Exception:
                default_model = "gemini-3.1-flash-lite"
            st.session_state.model_name = default_model
        elif selected_provider == "OpenAI":
            st.session_state.model_name = "gpt-4o-mini"
        elif selected_provider == "Anthropic Claude":
            st.session_state.model_name = "claude-3-5-sonnet-latest"
        st.rerun()

    # Input del modelo
    model_input = st.text_input("Nombre del Modelo", value=st.session_state.model_name)
    if model_input != st.session_state.model_name:
        st.session_state.model_name = model_input

    # Obtener placeholder/default de la API Key de la variable de entorno correspondiente
    env_key = ""
    if st.session_state.provider == "Google Gemini":
        env_key = os.environ.get("GOOGLE_API_KEY", "")
    elif st.session_state.provider == "OpenAI":
        env_key = os.environ.get("OPENAI_API_KEY", "")
    elif st.session_state.provider == "Anthropic Claude":
        env_key = os.environ.get("ANTHROPIC_API_KEY", "")

    placeholder_text = "Usar clave de variable de entorno" if env_key else "Ingresa tu API Key"
    
    # Input de la API Key (password para seguridad)
    api_key_input = st.text_input(
        "API Key / Token", 
        value=st.session_state.api_key if st.session_state.api_key != env_key else "", 
        type="password", 
        placeholder=placeholder_text
    )
    
    if st.button("Guardar Configuración 💾", use_container_width=True):
        key_to_save = api_key_input.strip() or env_key
        if not key_to_save:
            st.error("⚠️ Por favor proporciona una API Key o define la variable de entorno correspondiente.")
        else:
            with st.spinner("Inicializando modelo y agentes..."):
                try:
                    advisor, summary = create_executors(
                        st.session_state.provider, 
                        key_to_save, 
                        st.session_state.model_name
                    )
                    st.session_state.stack_advisor_executor = advisor
                    st.session_state.plan_summary_executor = summary
                    st.session_state.api_key = key_to_save
                    st.success("¡Configuración de IA cargada con éxito! 🎉")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al inicializar: {str(e)}")

    st.markdown("---")
    st.info(
        f"**Estado actual:**\nPaso: {st.session_state.chat_step.upper()}\n\n"
        f"**Directorio base:**\n`{DOCUMENTS_DIR}`"
    )

    if st.button("Reiniciar Conversación 🔄", use_container_width=True):
        reset_conversation()
        st.rerun()

# Muestra los mensajes
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Mensaje de advertencia si no se ha configurado la IA
if st.session_state.stack_advisor_executor is None:
    st.warning("⚠️ **Configuración de IA requerida:** Por favor, ingresa tu API Key en el panel de la barra lateral para poder interactuar con el asistente.")

# Checkpoint de Human-in-the-loop: se muestra solo en el paso de revisión
if st.session_state.chat_step == "review":
    col1, col2 = st.columns(2)
    approve = col1.button("✅ Aprobar e instalar", use_container_width=True)
    reject = col2.button("🔄 Rechazar / Modificar", use_container_width=True)

    if approve:
        stack = st.session_state.stack
        dest_path = st.session_state.destination_path

        with st.spinner("Validando gestores de paquetes requeridos..."):
            missing = check_missing_binaries(stack["binaries"])

        if missing:
            from agent_project_initializer import attempt_auto_install
            for binary in list(missing):
                with st.spinner(f"Intentando instalar automáticamente la herramienta faltante: {binary}..."):
                    attempt_auto_install(binary)
            
            with st.spinner("Revalidando herramientas instaladas..."):
                missing = check_missing_binaries(stack["binaries"])

        if missing:
            error_msg = (
                f"❌ No se encontraron en el sistema las siguientes herramientas requeridas: "
                f"**{', '.join(missing)}**. Instálalas y presiona nuevamente 'Aprobar e instalar'."
            )
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            st.rerun()
        else:
            with st.spinner(f"Creando estructura del proyecto en {dest_path}..."):
                structure_error = create_project_structure(dest_path, stack)

            if structure_error:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"{structure_error}\n\n**¿En qué carpeta dentro de 'Documents' deseas crear el proyecto?**"
                })
                st.session_state.chat_step = "path"
                st.rerun()
            else:
                with st.spinner(f"Instalando dependencias con {stack['manager']}..."):
                    success, output = install_dependencies(dest_path, stack)

                if success:
                    final_msg = (
                        f"✅ ¡Proyecto listo para ejecutarse! Se creó la estructura en `{dest_path}` "
                        f"y se instalaron las dependencias con `{' '.join(stack['install_cmd'])}`.\n\n"
                        f"```\n{output}\n```"
                    )
                else:
                    final_msg = (
                        f"⚠️ La estructura del proyecto se creó en `{dest_path}`, pero la instalación de "
                        f"dependencias falló:\n\n```\n{output}\n```"
                    )
                st.session_state.messages.append({"role": "assistant", "content": final_msg})
                st.session_state.chat_step = "done"
                st.rerun()

    if reject:
        st.session_state.messages.append({
            "role": "assistant",
            "content": (
                "Entendido, detengo el proceso de instalación. Cuéntame qué ajustes necesitas y "
                "empecemos de nuevo: **¿qué tipo de proyecto deseas iniciar? (Web / Mobile)**"
            )
        })
        st.session_state.project_type = None
        st.session_state.stack = None
        st.session_state.destination_path = None
        st.session_state.chat_step = "type"
        st.rerun()

# Entrada conversacional del usuario (deshabilitada si no hay ejecutor activo)
chat_disabled = st.session_state.stack_advisor_executor is None
if prompt := st.chat_input("Escribe tu respuesta aquí...", disabled=chat_disabled):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    if st.session_state.chat_step == "type":
        error = validate_mandatory_answer(prompt)
        project_type = None
        if not error:
            project_type = normalize_project_type(prompt)
            if project_type is None:
                error = "⚠️ Por favor responde 'Web' o 'Mobile' para continuar."

        with st.chat_message("assistant"):
            if error:
                st.markdown(error)
                st.session_state.messages.append({"role": "assistant", "content": error})
            else:
                st.session_state.project_type = project_type
                with st.spinner("Consultando árbol de decisión de stacks tecnológicos..."):
                    try:
                        res = st.session_state.stack_advisor_executor.invoke(
                            {"input": f"Recomienda los stacks disponibles para un proyecto de tipo: {project_type}"}
                        )
                        response_text = res["output"]
                    except Exception as e:
                        response_text = f"❌ Ocurrió un error al recomendar el stack:\n\n`{str(e)}`\n\nPor favor, intenta de nuevo."

                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
                st.session_state.chat_step = "stack"
            st.rerun()

    elif st.session_state.chat_step == "stack":
        error = validate_mandatory_answer(prompt)
        stack = None
        if not error:
            stack = resolve_stack_choice(st.session_state.project_type, prompt)
            if stack is None:
                error = "⚠️ Esa opción no es válida. Por favor selecciona uno de los stacks numerados anteriormente."

        with st.chat_message("assistant"):
            if error:
                st.markdown(error)
                st.session_state.messages.append({"role": "assistant", "content": error})
            else:
                st.session_state.stack = stack
                response_text = (
                    f"Elegiste **{stack['name']}**. Ahora, ¿en qué carpeta dentro de tu directorio "
                    f"**'Documents'** deseas crear el proyecto? (ej. `mi-proyecto`)"
                )
                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
                st.session_state.chat_step = "path"
            st.rerun()

    elif st.session_state.chat_step == "path":
        error = validate_mandatory_answer(prompt)

        with st.chat_message("assistant"):
            if error:
                st.markdown(error)
                st.session_state.messages.append({"role": "assistant", "content": error})
            else:
                dest_path = resolve_destination_path(prompt)
                st.session_state.destination_path = dest_path
                stack = st.session_state.stack

                plan_data = (
                    f"Tipo de proyecto: {st.session_state.project_type}\n"
                    f"Stack: {stack['name']} (gestor: {stack['manager']})\n"
                    f"Ruta destino: {dest_path}\n"
                    f"Estructura a crear: {stack['structure_summary']}\n"
                    f"Comando de instalación: {' '.join(stack['install_cmd'])}"
                )

                with st.spinner("Preparando plan de instalación para tu revisión..."):
                    try:
                        res = st.session_state.plan_summary_executor.invoke({"input": plan_data})
                        response_text = res["output"]
                    except Exception as e:
                        response_text = f"❌ Ocurrió un error al preparar el plan de instalación:\n\n`{str(e)}`\n\nPor favor, intenta de nuevo."

                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
                st.session_state.chat_step = "review"
            st.rerun()

    elif st.session_state.chat_step == "review":
        with st.chat_message("assistant"):
            reminder = "Por favor utiliza los botones de aprobación que aparecen arriba para continuar (✅ Aprobar / 🔄 Rechazar)."
            st.markdown(reminder)
            st.session_state.messages.append({"role": "assistant", "content": reminder})

    elif st.session_state.chat_step == "done":
        with st.chat_message("assistant"):
            info_msg = "El proyecto ya fue inicializado. Usa 'Reiniciar Conversación' en la barra lateral para crear otro proyecto."
            st.markdown(info_msg)
            st.session_state.messages.append({"role": "assistant", "content": info_msg})


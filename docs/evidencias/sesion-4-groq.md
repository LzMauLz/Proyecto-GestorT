# Sesión 4 · Respuesta de Groq en la demo pública

El 18 de noviembre de 2026 se abrió **Añadir producto** en la [demo pública de GestorTech](https://gestortech.pythonanywhere.com/) con una sesión de administrador. Se seleccionó **Redactar descripción con IA** para un producto ficticio.

El formulario envió `POST https://gestortech.pythonanywhere.com/products/suggest-description` con el nombre `Cable USB-C de demostración, 1 metro`, la categoría `Accesorio` y una descripción vacía.

El formulario confirmó «Descripción sugerida. Revísala antes de guardar.» y copió este valor del campo `description` de la respuesta JSON.

```json
{
  "description": "Cable USB‑C de 1 metro diseñado para demostraciones y pruebas de conectividad."
}
```

La descripción quedó en el formulario para revisión. El producto de prueba no se guardó ni se publicó.

Para reproducir la comprobación desde el panel, abre **Inventario → Añadir producto**, escribe un nombre ficticio, elige una categoría y pulsa **Redactar descripción con IA**. La ruta requiere la sesión del administrador y la protección CSRF que incorpora el formulario.

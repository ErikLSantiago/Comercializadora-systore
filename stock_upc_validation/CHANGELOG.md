# Changelog

## 18.0.1.12.2

- Corrige Packing/Empaque para que el check **El producto no cuenta con UPC/EAN** también omita la validación obligatoria de NS/IMEI.
- Bloquea el campo NS/IMEI cuando la línea está marcada como producto sin UPC/EAN.
- Habilita eliminación de líneas en los wizards para procesar parciales.
- Ajusta cantidades procesadas antes de validar para que las líneas eliminadas no se procesen y Odoo mantenga su flujo nativo de backorder.

## 18.0.1.12.1

- Corrige apertura del wizard completo de Empaque con UPC/EAN + NS/IMEI + guía.

## 18.0.1.12.0

- Agrega checkbox por línea **El producto no cuenta con UPC/EAN**.
- Permite omitir validación UPC/EAN sólo en líneas seleccionadas.
- Registra en chatter usuario y productos omitidos.

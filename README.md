# Biomed POS — Punto de Venta en Python

Sistema de punto de venta de escritorio desarrollado en Python con Tkinter, orientado a negocios de artículos ortopédicos y de rehabilitación. Usa SQLite como motor de base de datos y genera tickets en PDF.

## Características

- **Caja** — registro de ventas, métodos de pago (efectivo / tarjeta), cálculo automático de cambio e IVA
- **Inventario** — alta, baja y edición de productos con SKU, categoría, marca, talla/color, costo y precio
- **Recepciones** — entrada de mercancía con actualización automática de stock
- **Pedidos** — órdenes de compra a proveedores
- **Rentas** — módulo de préstamo/renta de equipo ortopédico con seguimiento de devoluciones
- **Clientes** — directorio con historial de compras y niveles de precio
- **Empleados y Checador** — registro de personal y control de asistencia
- **Cortes y Reportes** — cortes semanales/mensuales, desglose de ventas y gastos, totales netos
- **Análisis** — gráficas de ventas por período generadas con Matplotlib
- **Tickets PDF** — ticket de venta generado automáticamente con fpdf2
- **Multi-usuario** — acceso por PIN con niveles (CEO / Gerente / Vendedor)

## Tecnologías

| Componente | Herramienta |
|---|---|
| GUI | Python 3 + Tkinter / ttk |
| Base de datos | SQLite 3 |
| Gráficas | Matplotlib |
| Tickets | fpdf2 |
| Imágenes | Pillow |

## Estructura del proyecto

```
POS/
├── POS.py              # Aplicación principal
├── DATA/
│   ├── biomed.db       # Base de datos SQLite  ← no incluida en el repo
│   └── icon_search.png
├── Logo_azul.png
└── Logo_blanco.png
```

> Los archivos `DATA/biomed.db`, logs y tickets PDF no se suben al repositorio (ver `.gitignore`).

## Instalación

```bash
# Clonar el repositorio
git clone https://github.com/JardiGarci/PointOfSale.git
cd PointOfSale

# Instalar dependencias
pip install fpdf2 matplotlib pillow

# Ejecutar
python POS.py
```

La base de datos se crea automáticamente en `DATA/biomed.db` al primer arranque.

## Autor

Jardi García — Ingeniería Biónica | Maestría en Sistemas Complejos  
[LinkedIn](https://www.linkedin.com/in/jardigarcia/)

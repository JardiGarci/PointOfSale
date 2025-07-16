# Point of Sale System (POS) in Python

This project is a Point of Sale (POS) system developed in Python with a graphical user interface built using `Tkinter`. It is designed for small and medium-sized businesses that need a simple tool to manage sales, products, users, and reports.

## Features

- 🎯 **Product management**: Add, search, and modify products.
- 💰 **Sales recording**: Automatically calculates totals and saves sales details to file.
- 👥 **User control**: Different access levels (Admin and Salesperson).
- 📄 **Reports**: Inventory and sales reports (accessible only to admins).
- 💾 **Data persistence**: Products and sales are saved locally in CSV files.
- 🧩 **Intuitive interface**: Built with `Tkinter` for ease of use.

## Technologies Used

- Python 3
- Tkinter (GUI)
- `csv` module for file-based data storage
- Object-Oriented Programming principles

## System Structure

```text
POS.py
├── Product class
├── Sale class
├── User class
├── PuntoVentaApp class (main window)
│   ├── Login screen
│   ├── Main menu
│   ├── Management windows (products, sales, reports)
│   └── Access control system
└── Generated files:
    ├── productos.csv
    ├── ventas.csv

```
## Installation

1. Clone this repository:
```bash
git clone https://github.com/JardiGarci/PointOfSale
```

2. Run the scripts:
```bash
    python POS.py
    ```
Make sure Python 3 and Tkinter are installed on your system.

## Screenshots
(You can add screenshots of the system in action here)

## Possible Improvements
Add database integration (SQLite or MySQL)

- Generate PDF reports
- More robust inventory system with stock alerts
- Modernize the UI using ttk or customTkinter

## Author
Jardi Yulistian García Bustamante
Developed as a personal project to strengthen software development skills.

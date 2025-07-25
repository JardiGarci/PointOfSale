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
<img width="1375" height="798" alt="image" src="https://github.com/user-attachments/assets/0f501f4c-0146-433c-9bb6-a5083f9497af" />

<img width="1375" height="798" alt="image" src="https://github.com/user-attachments/assets/3f466cb3-32c2-46e3-8135-8392bbdb3a09" />

<img width="1375" height="798" alt="image" src="https://github.com/user-attachments/assets/5e98d296-945e-4da6-9d31-d1fc764bebde" />



## Possible Improvements
Add database integration (SQLite or MySQL)

- Generate PDF reports
- More robust inventory system with stock alerts
- Modernize the UI using `ttk` or `customTkinter`

## Author
Jardi Yulistian García Bustamante

Developed as a personal project to strengthen software development skills.

import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog, messagebox
import numpy as np
import os
from datetime import datetime, timedelta




class PuntoDeVenta:
    def __init__(self, root):
        self.root = root

        self.root.resizable(False, False)  # This code helps to disable windows from resizing
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        window_height = int(self.screen_height*0.85); window_width = int(self.screen_width*0.95)
        x_cordinate = int((self.screen_width/2) - (window_width/2));y_cordinate = int((self.screen_height*0.9/2) - (window_height/2))
        self.root.geometry("{}x{}+{}+{}".format(window_width, window_height, x_cordinate, y_cordinate))

        self.root.title("Biomed")
        self.screen_width = root.winfo_screenwidth()
        self.screen_height = root.winfo_screenheight()

        # path = os.path.join(os.path.dirname(os.path.abspath(__file__)),"path")
        path = os.path.dirname(os.path.abspath(__file__))
        self.path = os.path.join(path,"DATA")
        # self.path = os.path.dirname(os.path.abspath(__file__))
        # self.path = open(path, "r").read()

        # Información Productos
        self.path_data_products = os.path.join(self.path, "data_products.npz")

        # Información de usuarios
        self.path_data_users = os.path.join(self.path, "data_users.npz")
        
        # Información de estado de caja
        self.path_data_state = os.path.join(self.path, "data_state.npz")
        self.data_state = np.load(self.path_data_state, allow_pickle=True)["data"].item()
        
        # Información de Ordenes
        self.path_data_orders = os.path.join(self.path, "data_orders.npz")
        self.data_orders = np.load(self.path_data_orders, allow_pickle=True)["data"].item()

        self.icon_search = tk.PhotoImage(file=os.path.join(self.path,"icon_search.png"))
        self.icon_search = self.icon_search.subsample(13,13)

        self.index_precio = 10   # Posición del precio en el diccionario


        # Solicitando contraseña (Inicio punto de venta y opciones)
        self.solicitar_contraseña()

        # self.orders = np.load(self.path_data_orders, allow_pickle=True)["data"].item()
        self.data_clients = {"Publico General": {"cel": "NA", "Precio": 1 },"Jardi García":{"cel" : "9513024669" , "Precio":3}}


    
### ------------------------- Usuario Contraseña ----------------------------------------

    def solicitar_contraseña(self):

        for frame in self.root.winfo_children():
            frame.destroy()

        data = np.load(self.path_data_users, allow_pickle=True)["data"].item()

        contraseñas = np.array(data["keys"])
        usuario = np.array(data["users"])
        acceso = np.array(data["access"])
        photos = np.array(data["photos"])
        top = np.array(data["top"])
        

        contraseña = simpledialog.askstring("Usuario", "Ingrese su pin:", show='*')

        if contraseña in contraseñas:
            self.usuario = usuario[np.where(contraseñas == contraseña)][0]
            self.prioridad_usuario = acceso[np.where(contraseñas == contraseña)][0]
            self.path_photo = os.path.join(self.path,"pictures",photos[np.where(contraseñas == contraseña)][0])
            self.umbral_usuario = top[np.where(contraseñas == contraseña)][0]
            self.iniciar_punto_de_venta()
            self.opciones()
            self.opcion_estado_general()
        else:
            messagebox.showwarning("Error", "Contraseña incorrecta.")
            self.root.destroy()
            
##### ---------------------- Funciones -------------------------------

    def FiltrarData(self, vendedor = False, cliente = False, metodo_pago = False, fecha_inicial = False, fecha_final = False):
        # path = "DATA"
        """
        Metodo de pago : Efectivo, Tarjeta
        """
        # # Información de Ordenes
        # path_data_orders = os.path.join(path, "data_orders.npz")
        data_orders = np.load(self.path_data_orders, allow_pickle=True)["data"].item()
        data_filter = data_orders.copy()
        date_format = "%d/%m/%Y"
        
        if fecha_inicial != False: date_initial = datetime.strptime(fecha_inicial, date_format)
        if fecha_final != False: date_final = datetime.strptime(fecha_final, date_format)
        
        for order, item in data_orders.items():
            date = datetime.strptime(item["Fecha"], date_format)
            
            if vendedor != False and order in data_filter:
                if item["Vendedor"] != vendedor:
                    data_filter.pop(order)
                    
            if cliente != False and order in data_filter:
                if item["Cliente"] != cliente:
                    data_filter.pop(order)
                    
            if metodo_pago != False and order in data_filter:
                if item["Metodo_pago"] != metodo_pago:
                    data_filter.pop(order)
            
            if fecha_inicial != False and order in data_filter:                    
                if date < date_initial:
                    data_filter.pop(order)
                    
            
            if fecha_final != False and order in data_filter:
                # date = datetime.strptime(item["Fecha"], date_format)
                if date > date_final:
                    data_filter.pop(order)
            
        return data_filter

    def cortes_mes(self, month, year):
        month_f = month + 1
        year_f = year
        if month_f == 13: 
            month_f = 1
            year_f += 1
        date_i = datetime(year, month, 1) - timedelta(3)
        date_f = datetime(year_f, month_f, 1) - timedelta(3)
        cortes = [
            f"{date_i.day}/{date_i.month}/{date_i.year}",
            f"07/{month}/{year}",
            f"14/{month}/{year}",
            f"21/{month}/{year}",
            f"{date_f.day}/{date_f.month}/{date_f.year}"]
        return cortes


### ------------------------- Estado General ----------------------------------------
    def opcion_estado_general(self):
        
        self.date_today = datetime.now()
        datestr = f"{self.date_today.day}/{self.date_today.month}/{self.date_today.year}"
        cortes = self.cortes_mes(self.date_today.month, self.date_today.year)
        
        def actualizar_ordenes(ventas_usuario):
            def calcular_descuento(item):
                descuento = 0
                for i,item_producto in item["Productos"].items():
                    descuento += item_producto["Descuento"]
                return f"$ {descuento:4.2f}"
            for item in self.tree_orders.get_children():
                    self.tree_orders.delete(item)
            for order, item in ventas_usuario.items():
                self.tree_orders.insert('', 'end', text=order, values=(order,item["Fecha"],item["Hora"],item["Cliente"],item["Vendedor"],calcular_descuento(item),f'$ {item["Importe_total"]}'))
        
        def plazo_selected(event = None):
            plazo = self.combobox_plazo.get()
            if plazo == "Hoy":
                actualizar_ordenes(ventas_usuario_dia)
            else:
                actualizar_ordenes(ventas_usuario_mes)
                
        self.frame_estado = tk.Frame(self.root)
        self.frame_estado.place(x=self.screen_width*0.1,y=0,width=self.screen_width*0.9, height=self.screen_height)

        # Label Usuario
        self.label_usuario = tk.Label(self.frame_estado , text=f" ¡Hola {self.usuario}! ", font=("Arial",18))
        places = [0.33,0.02,0.1,0.1]
        self.label_usuario.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])


        # Label Caja
        self.label_caja = tk.Label(self.frame_estado , text=f" Caja ", font=("Arial",18))
        places = [0.1,0.11,0.2,0.05]
        self.label_caja.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        # Label Estado
        self.label_caja_estado = tk.Label(self.frame_estado , text=f" Estado :    {self.data_state['caja']}", font=("Arial",12), anchor='w')
        places = [0.1,0.17,0.2,0.03]
        self.label_caja_estado.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

        # Label Efectivo
        self.label_Efectivo = tk.Label(self.frame_estado , text=f" Efectivo:    ${self.data_state['efectivo']:5.2f} ", font=("Arial",12), anchor='w')
        places = [0.1,0.21,0.2,0.03]
        self.label_Efectivo.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        # Combox Hoy o Mes
        self.combobox_plazo = ttk.Combobox(self.frame_estado, state="readonly", values=["Hoy","Mes"], justify="center")
        places = [0.1,0.4,0.09,0.025]
        self.combobox_plazo.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        self.combobox_plazo.set(value=f"Hoy")
        self.combobox_plazo.bind("<<ComboboxSelected>>", plazo_selected)
        
        if self.prioridad_usuario <= 2:
            ventas_usuario_dia = self.FiltrarData(fecha_inicial=datestr)
            ventas_usuario_mes = self.FiltrarData(fecha_inicial=cortes[0])
        else:
            ventas_usuario_dia = self.FiltrarData(vendedor=self.usuario, fecha_inicial=datestr)
            ventas_usuario_mes = self.FiltrarData(vendedor=self.usuario, fecha_inicial=cortes[0])
        
        ventas = 0
        for order, item in ventas_usuario_mes.items():
            ventas += float(item["Importe_total"])
        
        venta_esperada = self.umbral_usuario
        p_comision = 7
        
        
        if ventas < venta_esperada:
            p_ventas = (ventas / venta_esperada) * 100
            comision = 0
        else:
            p_ventas = 100
            comision = (ventas - venta_esperada) * (p_comision / 100)
         
        
        # Progressbar
        progressbar = ttk.Progressbar(self.frame_estado, orient=tk.HORIZONTAL, length=160)
        places = [0.5,0.15,0.2,0.03]
        progressbar.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        progressbar.step(int(p_ventas))

        
        # Label Porcentaje
        label_percent = tk.Label(self.frame_estado , text=f"{np.round(p_ventas)} %", font=("Arial",14), anchor='w')
        places = [0.59,0.18,0.1,0.03]
        label_percent.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        
        # Label Venta Esperada
        label_venta_esperada = tk.Label(self.frame_estado , text=f"Venta esperada : ", font=("Arial",12), anchor='w')
        places = [0.5,0.25,0.1,0.03]
        label_venta_esperada.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        # Label Venta Esperada
        label_venta_esperada_val = tk.Label(self.frame_estado , text=f"$ {venta_esperada:2.2f}", font=("Arial",12), anchor='e')
        places = [0.6,0.25,0.1,0.03]
        label_venta_esperada_val.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        
        # Label Venta 
        label_venta = tk.Label(self.frame_estado , text=f"Venta del mes : ", font=("Arial",12), anchor='w')
        places = [0.5,0.3,0.1,0.03]
        label_venta.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        # Label Venta 
        label_venta_val = tk.Label(self.frame_estado , text=f"$ {ventas:2.2f}", font=("Arial",12), anchor='e')
        places = [0.6,0.3,0.1,0.03]
        label_venta_val.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        
        # Label comision 
        label_comision = tk.Label(self.frame_estado , text=f"Comision : ", font=("Arial",12), anchor='w')
        places = [0.5,0.35,0.1,0.03]
        label_comision.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        # Label Venta 
        label_comision_val = tk.Label(self.frame_estado , text=f"$ {comision:2.2f}", font=("Arial",12), anchor='e')
        places = [0.6,0.35,0.1,0.03]
        label_comision_val.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        
        self.tree_orders = ttk.Treeview(self.frame_estado, column=("ID", "Fecha", "Hora","Cliente","Vendedor","Descuento","Importe"), show='headings', height=15)
        places = [0.1,0.45,0.6,0.3]
        self.tree_orders.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        self.tree_orders.column("# 1", anchor=tk.CENTER, width=int(self.screen_width*0.05))
        self.tree_orders.heading("# 1", text="ID")
        self.tree_orders.column("# 2", anchor=tk.CENTER, width=int(self.screen_width*0.05))
        self.tree_orders.heading("# 2", text="Fecha")
        self.tree_orders.column("# 3", anchor=tk.CENTER, width=int(self.screen_width*0.05))
        self.tree_orders.heading("# 3", text="Hora")
        self.tree_orders.column("# 4", anchor=tk.CENTER, width=int(self.screen_width*0.15))
        self.tree_orders.heading("# 4", text="Cliente")
        self.tree_orders.column("# 5", anchor=tk.CENTER, width=int(self.screen_width*0.1))
        self.tree_orders.heading("# 5", text="Vendedor")
        self.tree_orders.column("# 6", anchor=tk.CENTER, width=int(self.screen_width*0.05))
        self.tree_orders.heading("# 6", text="Descuento")
        self.tree_orders.column("# 7", anchor=tk.CENTER, width=int(self.screen_width*0.05))
        self.tree_orders.heading("# 7", text="Importe")
        
        actualizar_ordenes(ventas_usuario_dia)
        
        
        
        


### ------------------------- Opciones ----------------------------------------
    def opciones(self):
        self.frame_Opciones = tk.Frame(self.root)
        self.frame_Opciones.place(x=0,y=0,width=self.screen_width*0.1, height=self.screen_height)

        # General
        self.boton_general = tk.Button(self.frame_Opciones, text=" General ", command=self.opcion_estado_general, font=("Arial",16))
        places = [0.01,0.03,0.08,0.05]
        self.boton_general.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

        # Caja
        self.boton_POS = tk.Button(self.frame_Opciones, text=" Caja ", command=self.opcion_punto_venta, font=("Arial",16))
        places = [0.01,0.1,0.08,0.05]
        self.boton_POS.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

        # Ordenes
        self.boton_orders = tk.Button(self.frame_Opciones, text=" Ordenes ", command=self.opcion_ordenes, font=("Arial",16))
        places = [0.01,0.17,0.08,0.05]
        self.boton_orders.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

        # Cambiar Usuario
        self.boton_sesion = tk.Button(self.frame_Opciones, text=" Cambiar Usuario ", command=self.solicitar_contraseña, font=("Arial",11))
        places = [0.01,0.78,0.08,0.05]
        self.boton_sesion.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

        if self.prioridad_usuario <= 2: # Opciones para CEO y Gerente
            # Cortes
            self.boton_reporte = tk.Button(self.frame_Opciones, text=" Corte ", command=self.opcion_reportes, font=("Arial",16))
            places = [0.01,0.24,0.08,0.05]
            self.boton_reporte.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

        if self.prioridad_usuario < 2: # Opciones para CEO
            # Cambiar Inventario
            self.boton_inventario = tk.Button(self.frame_Opciones, text=" Inventario ", command=self.opcion_inventario, font=("Arial",16))
            places = [0.01,0.31,0.08,0.05]
            self.boton_inventario.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])


    def iniciar_punto_de_venta(self):
        # Reinicia carrito
        self.carrito = {}
        self.Total = 0
        # Selecciona al cliente predeterminado
        self.cliente = "Publico General"
        self.data_products = np.load(self.path_data_products, allow_pickle=True)["data"].item()
        
        
### ------------------------ Reporte ---------------------------------------------------

    def dates_cortes(self):

        self.dates_orders = {}
        date_format = "%d/%m/%Y"
        for index, item in self.data_orders.items():
            date = datetime.strptime(item["Fecha"], date_format)
            if not date.month in self.dates_orders:
                self.dates_orders[date.month] = {"1":[(datetime(date.year, date.month - 1,28) + timedelta(i)).day for i in range(1,(datetime(date.year, date.month,8)-datetime(date.year, date.month - 1,28)).days)],
                                            "2":[(datetime(date.year, date.month ,7) + timedelta(i)).day for i in range(1,(datetime(date.year, date.month,15)-datetime(date.year, date.month ,7)).days)],
                                            "3":[(datetime(date.year, date.month ,14) + timedelta(i)).day for i in range(1,(datetime(date.year, date.month,22)-datetime(date.year, date.month ,14)).days)],
                                            "4":[(datetime(date.year, date.month ,21) + timedelta(i)).day for i in range(1,(datetime(date.year, date.month,29)-datetime(date.year, date.month ,21)).days)]}
    
    def years_orders(self):
        years = []
        date_format = "%d/%m/%Y"
        for index, item in self.data_orders.items():
            date = datetime.strptime(item["Fecha"], date_format)
            if not date.year in years:
                years.append(date.year)
        return years
        
    def cortes(self, year, month, n_cortes = 0, mes = False):
        month_f = month + 1
        year_f = year
        if month_f == 13: 
            month_f = 1
            year_f += 1
        cortes =[
            datetime(year, month, 1) - timedelta(3),
            datetime(year, month, 7),
            datetime(year, month, 14),
            datetime(year, month, 21),
            datetime(year, month_f, 1) - timedelta(3)
        ]
        if mes == False:
            if n_cortes == 0:
                date = datetime.now()
                for i,d in enumerate(cortes):
                    if d.date() >= date.date():
                        n_cortes = i
                        break
                    
            date_i = cortes[n_cortes - 1] + timedelta(1)
            date_f = cortes[n_cortes]
        else:
            date_i = cortes[0] + timedelta(1)
            date_f = cortes[-1]
            
        self.n_cortes = n_cortes
        
        str_date_i = f"{self.ajusta(date_i.day)}/{self.ajusta(date_i.month)}/{date_i.year}"
        str_date_f = f"{self.ajusta(date_f.day)}/{self.ajusta(date_f.month)}/{date_f.year}"
    
        return str_date_i, str_date_f
        
    
    def opcion_reportes(self):
        
        def year_selected(event = None):
            self.report_year = int(self.combobox_ano.get())
            
        def month_selected(event = None):
            self.report_month = int(self.combobox_mes.get())
            self.date_i, self.date_f = self.cortes(self.report_year, self.report_month, mes=True)
            self.ventas_filtradas = self.filtrar_orders(fecha_inicial=self.date_i,fecha_final=self.date_f)
            self.actualizar_ventas()
            self.combobox_corte.set(value=" -- ")
        
        def corte_selected(event = None):
            n_corte = int(self.combobox_corte.get())
            self.date_i, self.date_f = self.cortes(self.report_year, self.report_month, n_cortes= n_corte)
            self.ventas_filtradas = self.filtrar_orders(fecha_inicial=self.date_i,fecha_final=self.date_f)
            self.actualizar_ventas()
            
        
        date_now = datetime.now()
        self.report_month = date_now.month
        self.report_year = date_now.year
        self.date_i, self.date_f = self.cortes(self.report_year, self.report_month)
        # date_i, date_f = self.cortes(date_now.year, date_now.month)
        
        
        # self.dates_cortes()
        vals_years = self.years_orders()
        
        
        self.frame_reportes = tk.Frame(self.root)
        self.frame_reportes.place(x=self.screen_width*0.1,y=0,width=self.screen_width*0.9, height=self.screen_height)
        
        self.combobox_corte = ttk.Combobox(self.frame_reportes, state="readonly", values=[1,2,3,4], justify="center")
        places = [0.08,0.04,0.09,0.025]
        self.combobox_corte.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        self.combobox_corte.set(value=f"{self.n_cortes}")
        self.combobox_corte.bind("<<ComboboxSelected>>", corte_selected)
        
        self.combobox_mes = ttk.Combobox(self.frame_reportes, state="readonly", values=[1,2,3,4,5,6,7,8,9,10,11,12], justify="center")
        places = [0.2,0.04,0.09,0.025]
        self.combobox_mes.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        self.combobox_mes.set(value=self.report_month)
        self.combobox_mes.bind("<<ComboboxSelected>>", month_selected)
        
        self.combobox_ano = ttk.Combobox(self.frame_reportes, state="readonly", values=vals_years, justify="center")
        places = [0.32,0.04,0.09,0.025]
        self.combobox_ano.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        self.combobox_ano.set(value=self.report_year)
        self.combobox_ano.bind("<<ComboboxSelected>>", year_selected)
        
        
        # Ventas
        self.label_ventas_total = tk.Label(self.frame_reportes, text= "Ventas : ", font=("Arial",16))
        places = [0.55,0.23,0.1,0.05]
        self.label_ventas_total.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        self.label_ventas_total_value = tk.Label(self.frame_reportes, text= "$ 0.00 ", font=("Arial",16))
        places = [0.65,0.23,0.1,0.05]
        self.label_ventas_total_value.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        self.tree_ventas = ttk.Treeview(self.frame_reportes, column=("Fecha","Producto","Cantidad", "Descuento","Importe"), show='headings', height=15)
        places = [0.01,0.1,0.5,0.5]
        self.tree_ventas.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        self.tree_ventas.column("# 1", anchor=tk.CENTER, width=int(self.screen_width*0.008))
        self.tree_ventas.heading("# 1", text="Fecha")
        self.tree_ventas.column("# 2", anchor=tk.CENTER, width=int(self.screen_width*0.1))
        self.tree_ventas.heading("# 2", text="Producto")
        self.tree_ventas.column("# 3", anchor=tk.CENTER, width=int(self.screen_width*0.005))
        self.tree_ventas.heading("# 3", text="Cantidad")
        self.tree_ventas.column("# 4", anchor=tk.CENTER, width=int(self.screen_width*0.005))
        self.tree_ventas.heading("# 4", text="Descuento")
        self.tree_ventas.column("# 5", anchor=tk.CENTER, width=int(self.screen_width*0.01))
        self.tree_ventas.heading("# 5", text="Importe")
        
        
        # Gastos
        self.tree_gastos = ttk.Treeview(self.frame_reportes, column=("Fecha","Concepto","Importe"), show='headings', height=15)
        places = [0.01,0.61,0.5,0.14]
        self.tree_gastos.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        self.label_gastos_total = tk.Label(self.frame_reportes, text= "Gastos : ", font=("Arial",16))
        places = [0.55,0.33,0.1,0.05]
        self.label_gastos_total.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        self.label_gastos_total_value = tk.Label(self.frame_reportes, text= "$ 0.00 ", font=("Arial",16))
        places = [0.65,0.33,0.1,0.05]
        self.label_gastos_total_value.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        self.tree_gastos.column("# 1", anchor=tk.CENTER, width=int(self.screen_width*0.008))
        self.tree_gastos.heading("# 1", text="Fecha")
        self.tree_gastos.column("# 2", anchor=tk.CENTER, width=int(self.screen_width*0.2))
        self.tree_gastos.heading("# 2", text="Concepto")
        self.tree_gastos.column("# 3", anchor=tk.CENTER, width=int(self.screen_width*0.005))
        self.tree_gastos.heading("# 3", text="Importe")
        
        self.boton_agregar_gasto = tk.Button(self.frame_reportes, text="Agregar gasto", command=self.agregar_gasto)
        places = [0.41,0.76,0.1,0.05]
        self.boton_agregar_gasto.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

        # Total
        self.label_total = tk.Label(self.frame_reportes, text= "Total : ", font=("Arial",16))
        places = [0.55,0.43,0.1,0.05]
        self.label_total.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        self.label_total_value = tk.Label(self.frame_reportes, text= "$ 0.00 ", font=("Arial",16))
        places = [0.65,0.43,0.1,0.05]
        self.label_total_value.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        # Fechas
        self.label_fecha_inicio = tk.Label(self.frame_reportes, text= "Inicio :", font=("Arial",16))
        places = [0.55,0.1,0.1,0.05]
        self.label_fecha_inicio.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        self.label_fecha_inicio_val = tk.Label(self.frame_reportes, text= "--", font=("Arial",16))
        places = [0.65,0.1,0.1,0.05]
        self.label_fecha_inicio_val.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        self.label_fecha_fin = tk.Label(self.frame_reportes, text= "Fin :", font=("Arial",16))
        places = [0.55,0.15,0.1,0.05]
        self.label_fecha_fin.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        self.label_fecha_fin_val = tk.Label(self.frame_reportes, text= "--", font=("Arial",16))
        places = [0.65,0.15,0.1,0.05]
        self.label_fecha_fin_val.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        self.ventas_filtradas = self.filtrar_orders(fecha_inicial=self.date_i,fecha_final=self.date_f)
        self.actualizar_ventas()
        
    def agregar_gasto(self):
        Window = tk.Toplevel(self.root)
        Window.title("Gastos")

        window_height = int(self.screen_height*0.3); window_width = int(self.screen_width*0.3)
        x_cordinate = int((self.screen_width/2) - (window_width/2));y_cordinate = int((self.screen_height*0.9/2) - (window_height/2))
        Window.geometry("{}x{}+{}+{}".format(window_width, window_height, x_cordinate, y_cordinate))
        
        # Fecha
        label_fecha = tk.Label(Window, text= "Fecha", anchor="w")
        places = [0.1,0.05,0.2,0.15]
        label_fecha.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        
        # Concepto    
        label_concepto = tk.Label(Window, text= "Concepto", anchor="w")
        places = [0.1,0.3,0.2,0.15]
        label_concepto.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        entry_concepto = tk.Entry(Window)
        places = [0.35,0.3,0.6,0.15]
        entry_concepto.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        # Importe
        label_importe = tk.Label(Window, text= "Importe", anchor="w")
        places = [0.1,0.55,0.2,0.15]
        label_importe.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        entry_importe = tk.Entry(Window)
        places = [0.35,0.55,0.6,0.15]
        entry_importe.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        
        # Botón para guardar cambios
        button_guardar = tk.Button(Window, text=" Guardar ")
        places = [0.75,0.75,0.15,0.15]
        button_guardar.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        
        
    def actualizar_ventas(self):
        self.venta_total = 0
        self.gasto_total = 0
        for item in self.tree_ventas.get_children():
                self.tree_ventas.delete(item)
        for index,item in self.ventas_filtradas.items():
            for index_producto, item_producto in item["Productos"].items():
                self.venta_total += float(item_producto["Importe"])
                self.tree_ventas.insert('', 'end', text=index, values=(item["Fecha"],               # Fecha
                                                                        self.data_products[index_producto][2],                        # Producto
                                                                        item_producto["Cantidad"],  # Cantidad
                                                                        f'$ {item_producto["Descuento"]:4.2f}', # Descuento
                                                                        f'$ {item_producto["Importe"]:4.2f}',   # Importe
                ))
                
        self.actualizar_labels_reportes()
        
    
    def actualizar_labels_reportes(self):
        total = self.venta_total - self.gasto_total
        
        self.label_ventas_total_value.config(text=f"$ {self.venta_total:4.2f}")
        self.label_total_value.config(text=f"$ {total:4.2f}")
        self.label_fecha_inicio_val.config(text= f"{self.date_i}")
        self.label_fecha_fin_val.config(text= f"{self.date_f}")
        
            
    def filtrar_orders(self, usuario = "", fecha_inicial = "", fecha_final = ""):
        ordenes_filtradas = {}
        date_format = "%d/%m/%Y"
        if fecha_inicial != "": date_i = datetime.strptime(fecha_inicial, date_format)
        if fecha_final != "": 
            date_f = datetime.strptime(fecha_final, date_format)
        else:
            date_f = datetime.now()
        for id, item in self.data_orders.items():            
            if usuario == "" or item["Vendedor"] == usuario:
                date = datetime.strptime(item["Fecha"], date_format)
                if fecha_inicial != "": 
                    if date >= date_i and date <= date_f:
                        ordenes_filtradas[id] = item
                else:
                    if date <= date_f:
                        ordenes_filtradas[id] = item
        return ordenes_filtradas  
### ------------------------- Inventario -----------------------------------------------

    def opcion_inventario(self):
        
        # self.boton_inventario.config(relief=tk.SUNKEN)
        
        self.data_products = np.load(self.path_data_products, allow_pickle=True)["data"].item()
        self.productos_filtrados = np.load(self.path_data_products, allow_pickle=True)["data"].item()

        self.frame_inventario = tk.Frame(self.root)
        self.frame_inventario.place(x=self.screen_width*0.1,y=0,width=self.screen_width*0.9, height=self.screen_height)

        # Barra de búsqueda
        self.entrada_busqueda = tk.Entry(self.frame_inventario)
        places = [0.055,0.045,0.35,0.03]
        self.entrada_busqueda.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        self.entrada_busqueda.bind("<KeyRelease>", self.buscar_producto_inventario)

        # Imagen Icon Search
        self.labe_icon_search = tk.Label(self.frame_inventario, image=self.icon_search)
        places = [0.02,0.04,0.03,0.05]
        self.labe_icon_search.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        # Boton agregar producto
        self.boton_agregar_producto = tk.Button(self.frame_inventario, text="Agregar", command=self.window_editar_inventario)
        places = [0.73,0.035,0.10,0.05]
        self.boton_agregar_producto.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        # Boton eliminar producto
        self.boton_eliminar_producto = tk.Button(self.frame_inventario, text="Eliminar", command=self.eliminar_producto)
        places = [0.62,0.035,0.10,0.05]
        self.boton_eliminar_producto.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        
        
        # Tabla de inventario
        self.tree_inventario = ttk.Treeview(self.frame_inventario, column=("ID","SKU", "PCU","Producto","Talla", "Categoria","Marca","Vendero","Cantidad","Costo","Precio"), show='headings', height=15)
        places = [0.01,0.1,0.81,0.7]
        self.tree_inventario.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        self.tree_inventario.column("# 1", anchor=tk.CENTER, width=int(self.screen_width*0.01))
        self.tree_inventario.heading("# 1", text="ID")
        self.tree_inventario.column("# 2", anchor=tk.CENTER, width=int(self.screen_width*0.01))
        self.tree_inventario.heading("# 2", text="SKU")
        self.tree_inventario.column("# 3", anchor=tk.CENTER, width=int(self.screen_width*0.017))
        self.tree_inventario.heading("# 3", text="PCU")
        self.tree_inventario.column("# 4", anchor=tk.CENTER, width=int(self.screen_width*0.2))
        self.tree_inventario.heading("# 4", text="Producto")
        self.tree_inventario.column("# 5", anchor=tk.CENTER, width=int(self.screen_width*0.015))
        self.tree_inventario.heading("# 5", text="Talla/Color")
        self.tree_inventario.column("# 6", anchor=tk.CENTER, width=int(self.screen_width*0.02))
        self.tree_inventario.heading("# 6", text="Categoria")
        self.tree_inventario.column("# 7", anchor=tk.CENTER, width=int(self.screen_width*0.015))
        self.tree_inventario.heading("# 7", text="Marca")
        self.tree_inventario.column("# 8", anchor=tk.CENTER, width=int(self.screen_width*0.015))
        self.tree_inventario.heading("# 8", text="Vendedor")
        self.tree_inventario.column("# 9", anchor=tk.CENTER, width=int(self.screen_width*0.01))
        self.tree_inventario.heading("# 9", text="Cantidad")
        self.tree_inventario.column("# 10", anchor=tk.CENTER, width=int(self.screen_width*0.01))
        self.tree_inventario.heading("# 10", text="Costo")
        self.tree_inventario.column("# 11", anchor=tk.CENTER, width=int(self.screen_width*0.01))
        self.tree_inventario.heading("# 11", text="Precio")
        
        self.tree_inventario.bind("<Double-Button-1>", self.editar_inventario)
        self.actualizar_tree_inventario()
    
    def eliminar_producto(self):
        
        
        def confirmar():
            self.data_products.pop(index)
            self.productos_filtrados.pop(index)
            np.savez(self.path_data_products, data = self.data_products)
            Window.destroy()
            self.actualizar_tree_inventario()
            
        
        def cancelar():
            Window.destroy()
        
        Window = tk.Toplevel(self.root)
        Window.title("Confirmar eliminar")
        window_height = int(self.screen_height*0.2); window_width = int(self.screen_width*0.3)
        x_cordinate = int((self.screen_width/2) - (window_width/2));y_cordinate = int((self.screen_height*0.9/2) - (window_height/2))
        Window.geometry("{}x{}+{}+{}".format(window_width, window_height, x_cordinate, y_cordinate))
        
        item = self.tree_inventario.selection()
        seleccion = self.tree_inventario.index(item)
        index = list(self.productos_filtrados.keys())[seleccion]
        
        label_confirmar = tk.Label(Window, text="Se eliminará el producto : ", font=("Arial",12))
        places = [0.1,0.1,0.8,0.1]
        label_confirmar.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        label_producto = tk.Label(Window, text=f"{self.data_products[index][2]} {self.data_products[index][5]}", font=("Arial",9))
        places = [0.1,0.3,0.8,0.1]
        label_producto.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        
        button_confirmar = tk.Button(Window, text= "Confirmar", command= confirmar, font=("Arial",15))
        places = [0.1,0.5,0.35,0.35]
        button_confirmar.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])

        button_cancelar = tk.Button(Window, text= "Cancelar", command= cancelar, font=("Arial",15))
        places = [0.55,0.5,0.35,0.35]
        button_cancelar.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])

        
    def buscar_producto_inventario(self, event=None):
        termino_busqueda = self.entrada_busqueda.get().lower()
        self.data_products = np.load(self.path_data_products, allow_pickle=True)["data"].item()
        self.productos_filtrados = {}
        for index, item in self.data_products.items():
            if self.find(item[:5],termino_busqueda):
                self.productos_filtrados[index] = item
        self.actualizar_tree_inventario()
        
    def actualizar_tree_inventario(self):
        for item in self.tree_inventario.get_children():
                self.tree_inventario.delete(item)
        for index,item in self.productos_filtrados.items():
            self.tree_inventario.insert('', 'end', text=index, values=(index,                          # ID
                                                                       item[0],                        # SKU
                                                                       item[1],                        # PCU
                                                                       item[2],                        # Producto
                                                                       item[5],                        # Talla/Color
                                                                       item[4],                        # Categoría
                                                                       item[6],                        # Marca
                                                                       item[7],                        # Vendedor
                                                                       item[8],                        # Cantidad
                                                                       item[9],                        # Costo
                                                                       item[10]                        # Precio
                                                                       ))
            
    def editar_inventario(self, event=None):
        
        item = self.tree_inventario.selection()
        seleccion = self.tree_inventario.index(item) + 1
        
        if seleccion:
            index = list(self.productos_filtrados.keys())[seleccion - 1]
            self.window_editar_inventario(index=index, item= item, item_producto = self.data_products[index])
            
            
    def window_editar_inventario(self,index = "", item = "", item_producto = ""):
        if not item_producto:
            index = f"{np.max(np.array(list(self.data_products.keys()), dtype=int)) + 1}"
            
            
        def aplicar_cambio():
            if not item_producto:
                self.data_products[index] = ["" for i in range(11)]
            try:
                self.data_products[index][0] =entry_sku.get()
                self.data_products[index][1] =entry_pcu.get()
                self.data_products[index][2] =entry_producto.get()
                self.data_products[index][5] =entry_talla.get()
                self.data_products[index][4] =entry_categoria.get()
                self.data_products[index][6] =entry_marca.get()
                self.data_products[index][7] =entry_vendedor.get()
                self.data_products[index][8] = int(entry_cantidad.get())
                self.data_products[index][9] = float(entry_costo.get())
                self.data_products[index][10] = float(entry_precio.get())
                
                np.savez(self.path_data_products, data = self.data_products)
                Window.destroy()
                self.productos_filtrados[index] = self.data_products[index]
                self.actualizar_tree_inventario()
            
            except:
                pass    
            
        
        Window = tk.Toplevel(self.root)
        Window.title("Información del producto")
        window_height = int(self.screen_height*0.6); window_width = int(self.screen_width*0.3)
        x_cordinate = int((self.screen_width/2) - (window_width/2));y_cordinate = int((self.screen_height*0.9/2) - (window_height/2))
        Window.geometry("{}x{}+{}+{}".format(window_width, window_height, x_cordinate, y_cordinate))
        
        label_id = tk.Label(Window, text= "ID ", font = ("Arial", 12), anchor='w')
        places = [0.1,0.06,0.2,0.05]
        label_id.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        entry_id = tk.Entry(Window, font = ("Arial", 12), justify="right")
        places = [0.4,0.06,0.5,0.05]
        entry_id.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        label_sku = tk.Label(Window, text= "SKU ", font = ("Arial", 12), anchor='w')
        places = [0.1,0.14,0.2,0.05]
        label_sku.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        entry_sku = tk.Entry(Window, font = ("Arial", 12), justify="right")
        places = [0.4,0.14,0.5,0.05]
        entry_sku.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        label_pcu = tk.Label(Window, text= "PCU ", font = ("Arial", 12), anchor='w')
        places = [0.1,0.22,0.2,0.05]
        label_pcu.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        entry_pcu = tk.Entry(Window, font = ("Arial", 12), justify="right")
        places = [0.4,0.22,0.5,0.05]
        entry_pcu.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        label_producto = tk.Label(Window, text= "Producto ", font = ("Arial", 12), anchor='w')
        places = [0.1,0.30,0.2,0.05]
        label_producto.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        entry_producto = tk.Entry(Window, font = ("Arial", 12), justify="right")
        places = [0.4,0.30,0.5,0.05]
        entry_producto.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        label_talla = tk.Label(Window, text= "Talla/Color ", font = ("Arial", 12), anchor='w')
        places = [0.1,0.38,0.2,0.05]
        label_talla.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        entry_talla= tk.Entry(Window, font = ("Arial", 12), justify="right")
        places = [0.4,0.38,0.5,0.05]
        entry_talla.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        label_categoria = tk.Label(Window, text= "Categoria ", font = ("Arial", 12), anchor='w')
        places = [0.1,0.46,0.2,0.05]
        label_categoria.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        entry_categoria = tk.Entry(Window, font = ("Arial", 12), justify="right")
        places = [0.4,0.46,0.5,0.05]
        entry_categoria.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        label_marca = tk.Label(Window, text= "Marca ", font = ("Arial", 12), anchor='w')
        places = [0.1,0.54,0.2,0.05]
        label_marca.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        entry_marca = tk.Entry(Window, font = ("Arial", 12), justify="right")
        places = [0.4,0.54,0.5,0.05]
        entry_marca.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        label_vendedor = tk.Label(Window, text= "Vendedor ", font = ("Arial", 12), anchor='w')
        places = [0.1,0.62,0.2,0.05]
        label_vendedor.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        entry_vendedor = tk.Entry(Window, font = ("Arial", 12), justify="right")
        places = [0.4,0.62,0.5,0.05]
        entry_vendedor.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        label_cantidad = tk.Label(Window, text= "Cantidad ", font = ("Arial", 12), anchor='w')
        places = [0.1,0.70,0.2,0.05]
        label_cantidad.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        entry_cantidad = tk.Entry(Window, font = ("Arial", 12), justify="right")
        places = [0.4,0.70,0.5,0.05]
        entry_cantidad.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
    
        label_costo = tk.Label(Window, text= "Costo ", font = ("Arial", 12), anchor='w')
        places = [0.1,0.78,0.2,0.05]
        label_costo.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        entry_costo = tk.Entry(Window, font = ("Arial", 12), justify="right")
        places = [0.4,0.78,0.5,0.05]
        entry_costo.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        label_precio = tk.Label(Window, text= "Precio ", font = ("Arial", 12), anchor='w')
        places = [0.1,0.86,0.2,0.05]
        label_precio.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        entry_precio = tk.Entry(Window, font = ("Arial", 12), justify="right")
        places = [0.4,0.86,0.5,0.05]
        entry_precio.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        button_aplicar = tk.Button(Window, text= "Aplicar", command= aplicar_cambio)
        places = [0.55,0.92,0.2,0.05]
        button_aplicar.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])

        entry_id.insert(0,index)
        entry_id.config(state="disabled")
        if item_producto:
            entry_sku.insert(0,item_producto[0])
            entry_pcu.insert(0,item_producto[1])
            entry_producto.insert(0,item_producto[2])
            entry_talla.insert(0,item_producto[5])
            entry_categoria.insert(0,item_producto[4])
            entry_marca.insert(0,item_producto[6])
            entry_vendedor.insert(0,item_producto[7])
            entry_cantidad.insert(0,item_producto[8])
            entry_costo.insert(0,item_producto[9])
            entry_precio.insert(0,item_producto[10])
    
        
### ------------------------- Ordenes -----------------------------------------------

    def opcion_ordenes(self):
        # self.ordenes_filtradas = self.data_orders
        self.data_products = np.load(self.path_data_products, allow_pickle=True)["data"].item()
        self.frame_ordenes = tk.Frame(self.root)
        self.frame_ordenes.place(x=self.screen_width*0.1,y=0,width=self.screen_width*0.9, height=self.screen_height)
    
        # Tabla de productos
        self.tree_orders = ttk.Treeview(self.frame_ordenes, column=("ID", "Fecha", "Hora","Cliente","Vendedor","Descuento","Importe"), show='headings', height=15)
        places = [0.1,0.05,0.65,0.7]
        self.tree_orders.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
        self.tree_orders.column("# 1", anchor=tk.CENTER, width=int(self.screen_width*0.05))
        self.tree_orders.heading("# 1", text="ID")
        self.tree_orders.column("# 2", anchor=tk.CENTER, width=int(self.screen_width*0.05))
        self.tree_orders.heading("# 2", text="Fecha")
        self.tree_orders.column("# 3", anchor=tk.CENTER, width=int(self.screen_width*0.05))
        self.tree_orders.heading("# 3", text="Hora")
        self.tree_orders.column("# 4", anchor=tk.CENTER, width=int(self.screen_width*0.15))
        self.tree_orders.heading("# 4", text="Cliente")
        self.tree_orders.column("# 5", anchor=tk.CENTER, width=int(self.screen_width*0.1))
        self.tree_orders.heading("# 5", text="Vendedor")
        self.tree_orders.column("# 6", anchor=tk.CENTER, width=int(self.screen_width*0.05))
        self.tree_orders.heading("# 6", text="Descuento")
        self.tree_orders.column("# 7", anchor=tk.CENTER, width=int(self.screen_width*0.05))
        self.tree_orders.heading("# 7", text="Importe")
        
        self.tree_orders.bind("<Double-Button-1>", self.modificar_ordenes)

        self.actualizar_ordenes()

    def modificar_ordenes(self, event = None):
        def eliminar_orden():
            
            self.data_state['efectivo'] -= self.data_orders[index]["Importe_total"]
            
            
            for id, products in self.data_orders[index]["Productos"].items():
                # print(id)
                # print(products)
                self.data_products[id][8] += products["Cantidad"]
            
            self.data_orders.pop(index)
            np.savez(self.path_data_orders, data = self.data_orders)
            np.savez(self.path_data_state, data = self.data_state)
            np.savez(self.path_data_products, data = self.data_products)
            Window.destroy()
            self.actualizar_ordenes()
        Window = tk.Toplevel(self.root)
        Window.title("Información del producto")
        window_height = int(self.screen_height*0.6); window_width = int(self.screen_width*0.5)
        x_cordinate = int((self.screen_width/2) - (window_width/2));y_cordinate = int((self.screen_height*0.9/2) - (window_height/2))
        Window.geometry("{}x{}+{}+{}".format(window_width, window_height, x_cordinate, y_cordinate))
        
        item = self.tree_orders.selection()
        seleccion = self.tree_orders.index(item) + 1
        
        boton_eliminar_order = tk.Button(Window, text="Eliminar Orden", command=eliminar_orden, font=("Arial",13))
        places = [0.7,0.85,0.2,0.06]
        boton_eliminar_order.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
                    
        if seleccion:
            list_index = list(self.data_orders.keys())
            list_index.reverse()
            index = list_index[seleccion - 1]
            # print(self.data_orders[index])
            y = 0
            for i,key in enumerate(self.data_orders[index].keys()):
                y += 0.06
                if key != "Productos":
                    
                    label = tk.Label(Window, text=f"{key}", anchor='w')
                    places = [0.1,y,0.35,0.05]
                    label.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
                        
                    label_val = tk.Label(Window, text=f"{self.data_orders[index][key]}", anchor='e')
                    places = [0.55,y,0.35,0.05]
                    label_val.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
                else:
                    
                    tree_producto = ttk.Treeview(Window, column=("Producto", "Cantidad","Descuento","Importe"), show='headings', height=15)
                    places = [0.1,y,0.8,0.4]
                    tree_producto.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
                    # place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
                    tree_producto.column("# 1", anchor=tk.CENTER, width=int(self.screen_width*0.18))
                    tree_producto.heading("# 1", text="Producto")
                    tree_producto.column("# 2", anchor=tk.CENTER, width=int(self.screen_width*0.005))
                    tree_producto.heading("# 2", text="Cant")
                    tree_producto.column("# 3", anchor=tk.CENTER, width=int(self.screen_width*0.015))
                    tree_producto.heading("# 3", text="Descuento")
                    tree_producto.column("# 4", anchor=tk.CENTER, width=int(self.screen_width*0.015))
                    tree_producto.heading("# 4", text="Importe")
                    
                    
                    for id,item_producto in self.data_orders[index]["Productos"].items():
                        tree_producto.insert('', 'end', text=index, values=(f"{self.data_products[id][2]} {self.data_products[id][5]}",
                                                                            item_producto["Cantidad"],
                                                                            f'{item_producto["Descuento"]:4.2f}',
                                                                            item_producto["Importe"])) 
                    
                    
                    y += 0.35
                
    def actualizar_ordenes(self):
        def calcular_descuento(item):
            descuento = 0
            for i,item_producto in item["Productos"].items():
                descuento += item_producto["Descuento"]
            return f"$ {descuento:4.2f}"
        
        for item in self.tree_orders.get_children():
                self.tree_orders.delete(item)
        # list_index = list(self.ordenes_filtradas.keys())
        list_index = list(self.data_orders.keys())
        list_index.reverse()
        for index in list_index:
            # item = self.ordenes_filtradas[index]
            item = self.data_orders[index]
            self.tree_orders.insert('', 'end', text=index, values=(index,item["Fecha"],item["Hora"],item["Cliente"],item["Vendedor"],calcular_descuento(item),f'$ {item["Importe_total"]}'))

    

### ------------------------- Punto de venta ----------------------------------------
    def opcion_punto_venta(self):
        self.frame_POS = tk.Frame(self.root)
        self.frame_POS.place(x=self.screen_width*0.1,y=0,width=self.screen_width*0.9, height=self.screen_height)

        # Carga la data
        self.data_products = np.load(self.path_data_products, allow_pickle=True)["data"].item()
        self.productos_filtrados = np.load(self.path_data_products, allow_pickle=True)["data"].item()

        if self.data_state['caja'] == "Abierta":
            # Barra de búsqueda
            self.entrada_busqueda = tk.Entry(self.frame_POS)
            places = [0.055,0.045,0.35,0.03]
            self.entrada_busqueda.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
            self.entrada_busqueda.bind("<KeyRelease>", self.buscar_producto)

            # Tabla de productos
            self.tree = ttk.Treeview(self.frame_POS, column=("SKU", "Producto","Marca","Cantidad","Precio"), show='headings', height=15)
            places = [0.0,0.1,0.45,0.7]
            self.tree.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
            self.tree.column("# 1", anchor=tk.CENTER, width=int(self.screen_width*0.01))
            self.tree.heading("# 1", text="SKU")
            self.tree.column("# 2", anchor="w", width=int(self.screen_width*0.2))
            self.tree.heading("# 2", text="Producto")
            self.tree.column("# 3", anchor=tk.CENTER, width=int(self.screen_width*0.013))
            self.tree.heading("# 3", text="Marca")
            self.tree.column("# 4", anchor=tk.CENTER, width=int(self.screen_width*0.003))
            self.tree.heading("# 4", text="Ext")
            self.tree.column("# 5", anchor=tk.CENTER, width=int(self.screen_width*0.015))
            self.tree.heading("# 5", text="Precio")

            # Tabla de carrito
            self.tree_carrito = ttk.Treeview(self.frame_POS, column=("Producto", "Cantidad","Descuento","Importe"), show='headings', height=15)
            places = [0.47,0.15,0.35,0.4]
            self.tree_carrito.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
            self.tree_carrito.column("# 1", anchor="w", width=int(self.screen_width*0.18))
            self.tree_carrito.heading("# 1", text="Producto")
            self.tree_carrito.column("# 2", anchor=tk.CENTER, width=int(self.screen_width*0.005))
            self.tree_carrito.heading("# 2", text="Cant")
            self.tree_carrito.column("# 3", anchor=tk.CENTER, width=int(self.screen_width*0.015))
            self.tree_carrito.heading("# 3", text="Desc")
            self.tree_carrito.column("# 4", anchor=tk.CENTER, width=int(self.screen_width*0.015))
            self.tree_carrito.heading("# 4", text="Importe")



            # Label vendedor
            self.label_vendedor = tk.Label(self.frame_POS , text=f" Usuario :   {self.usuario}", font=("Arial",12))
            places = [0.47,0.06,0.10,0.05]
            self.label_vendedor.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

            # Label cliente
            self.label_cliente = tk.Label(self.frame_POS , text=f" Cliente : ", font=("Arial",12))
            places = [0.64,0.06,0.10,0.05]
            self.label_cliente.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

            # Botón de cliente
            self.boton_cliente = tk.Button(self.frame_POS, text=f"{self.cliente}", command=self.client_Window, font=("Arial",12))
            places = [0.72,0.065,0.10,0.04]
            self.boton_cliente.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

            # Etiqueta para el subtotal
            self.etiqueta_subtotal = tk.Label(self.frame_POS, text="Subtotal:", font = ("Arial", 12))
            places = [0.62,0.56,0.15,0.04]
            self.etiqueta_subtotal.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

            # Etiqueta para el subtotal valor
            self.etiqueta_subtotal = tk.Label(self.frame_POS, text=f"$ {0:4.2f}", font = ("Arial", 12))
            places = [0.72,0.56,0.15,0.04]
            self.etiqueta_subtotal.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])


            # Etiqueta para el IVA
            self.etiqueta_IVA = tk.Label(self.frame_POS, text="IVA:", font = ("Arial", 12))
            places = [0.62,0.602,0.15,0.04]
            self.etiqueta_IVA.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

            # Etiqueta para el IVA valor
            self.etiqueta_IVA = tk.Label(self.frame_POS, text=f"$ {0:4.2f}", font = ("Arial", 12))
            places = [0.72,0.602,0.15,0.04]
            self.etiqueta_IVA.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])


            # Etiqueta para el total
            self.etiqueta_total = tk.Label(self.frame_POS, text="Total:", font = ("Arial", 15))
            places = [0.62,0.644,0.15,0.04]
            self.etiqueta_total.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])


            # Etiqueta para el total valor
            self.etiqueta_total = tk.Label(self.frame_POS, text=f"$ {0:4.2f}", font = ("Arial", 15))
            places = [0.72,0.644,0.15,0.04]
            self.etiqueta_total.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])


            # Botón para pagar
            self.boton_pagar = tk.Button(self.frame_POS, text="Pagar", command=self.pagar, font=("Arial",15))
            places = [0.52,0.63,0.115,0.05]
            self.boton_pagar.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

            # Botón para agregar
            self.boton_pagar = tk.Button(self.frame_POS, text=" + ", command=self.agregar_producto, font=("Arial",16))
            places = [0.6,0.57,0.035,0.05]
            self.boton_pagar.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

            # Botón para descuento
            self.boton_pagar = tk.Button(self.frame_POS, text=" % ", command=self.descuento_producto, font=("Arial",13))
            places = [0.56,0.57,0.035,0.05]
            self.boton_pagar.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
            
            # Botón para quitar
            self.boton_pagar = tk.Button(self.frame_POS, text=" - ", command=self.quitar_producto, font=("Arial",16))
            places = [0.52,0.57,0.035,0.05]
            self.boton_pagar.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

            # Imagen Icon Search
            self.labe_icon_search = tk.Label(self.frame_POS, image=self.icon_search)
            places = [0.02,0.04,0.03,0.05]
            self.labe_icon_search.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

            # Botón para Cerrar caja
            self.boton_cerrar_caja = tk.Button(self.frame_POS, text=" Cerrar Caja ", command = self.accion_caja, font=("Arial",15))
            places = [0.72,0.75,0.08,0.05]
            self.boton_cerrar_caja.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])
            
            # Botón para Reiniciar caja
            self.boton_cerrar_caja = tk.Button(self.frame_POS, text=" Borrar ", command = self.reiniciar_caja, font=("Arial",15))
            places = [0.63,0.75,0.08,0.05]
            self.boton_cerrar_caja.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])


            self.actualizar_tree_productos()
            self.tree.bind("<Double-Button-1>", self.agregar_al_carrito)
            self.actualizar_tree_carrito()

        else:
            # Label Abrir Caja
            self.label_abrir_caja = tk.Label(self.frame_POS , text=f" Necesitas abrir la caja para poder realizar ventas", font=("Arial",15))
            places = [0.2,0.15,0.35,0.35]
            self.label_abrir_caja.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

            # Botón para Abrir caja
            self.boton_abrir_caja = tk.Button(self.frame_POS, text=" Abrir Caja ", command = self.accion_caja, font=("Arial",15))
            places = [0.32,0.36,0.1,0.05]
            self.boton_abrir_caja.place(x=self.screen_width*places[0] ,y = self.screen_height*places[1], width=self.screen_width*places[2], height=self.screen_height*places[3])

    # ------- Caja
    def accion_caja(self):
   
        def total_caja(event = None):
            try:
                total = float(entry_billetes.get()) + float(entry_monedas.get())
                label_total_valor.configure(text=f" $ {total:5.2f}")        
            except:
                label_total_valor.configure(text=f" Error")
        
        def abrir():
            try:
                self.data_state['caja'] = "Abierta"
                self.data_state['efectivo'] = float(entry_billetes.get()) + float(entry_monedas.get())
                np.savez(self.path_data_state,data = self.data_state)
                self.opcion_punto_venta()
                cajaWindow.destroy()
            except:
                pass
            
        def cerrar():
            try:
                self.data_state['caja'] = "Cerrada"
                self.data_state['efectivo'] = 0
                np.savez(self.path_data_state,data = self.data_state)
                self.opcion_punto_venta()
                cajaWindow.destroy()
            except:
                pass
            
        
        cajaWindow = tk.Toplevel(self.root)
        cajaWindow.title("Caja")

        window_height = int(self.screen_height*0.25); window_width = int(self.screen_width*0.2)
        x_cordinate = int((self.screen_width/2) - (window_width/2));y_cordinate = int((self.screen_height*0.9/2) - (window_height/2))
        cajaWindow.geometry("{}x{}+{}+{}".format(window_width, window_height, x_cordinate, y_cordinate))
        
        label_billetes = tk.Label(cajaWindow, text=" Billetes :", font = ("Arial", 15))
        places = [0.1,0.1,0.30,0.15]
        label_billetes.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])

        
        entry_billetes = tk.Entry(cajaWindow, justify=tk.RIGHT, font=("Arial", 13))
        entry_billetes.insert(0,"0")
        places = [0.55,0.1,0.30,0.15]
        entry_billetes.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        entry_billetes.bind("<KeyRelease>", total_caja)
        
        label_monedas = tk.Label(cajaWindow, text=" Monedas :", font = ("Arial", 15))
        places = [0.1,0.3,0.30,0.15]
        label_monedas.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])

        
        entry_monedas = tk.Entry(cajaWindow, justify=tk.RIGHT, font=("Arial", 13))
        entry_monedas.insert(0,"0")
        places = [0.55,0.3,0.30,0.15]
        entry_monedas.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        entry_monedas.bind("<KeyRelease>", total_caja)

        label_total = tk.Label(cajaWindow, text=f" Total : ", font = ("Arial", 15))
        places = [0.1,0.5,0.3,0.15]
        label_total.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        
        label_total_valor = tk.Label(cajaWindow, text=f" $ 0.00", font = ("Arial", 15))
        places = [0.55,0.5,0.3,0.15]
        label_total_valor.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])

        if self.data_state['caja'] == "Cerrada":
            buttom_abrir = tk.Button(cajaWindow, text=" Abrir ", font = ("Arial", 15), command=abrir)
            places = [0.15,0.7,0.7,0.2]
            buttom_abrir.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        else:
            buttom_cerrar = tk.Button(cajaWindow, text=" Cerrar ", font = ("Arial", 15), command=cerrar)
            places = [0.15,0.7,0.7,0.2]
            buttom_cerrar.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
    
    def reiniciar_caja(self):
        self.carrito = {}
        self.actualizar_tree_carrito()

    # --------- Tabla productos
    def actualizar_tree_productos(self):
        for item in self.tree.get_children():
                self.tree.delete(item)
        for index,item in self.productos_filtrados.items():
            self.tree.insert('', 'end', text=index, values=(item[0],            # Código
                                                            f"{item[2]} -- ({item[5]})", # Producto
                                                            item[6],
                                                            item[8],            # Cantidad
                                                            f"$ {item[self.index_precio]:5.2f}")) # Precio
    def buscar_producto(self, event=None):
        termino_busqueda = self.entrada_busqueda.get().lower()
        self.data_products = np.load(self.path_data_products, allow_pickle=True)["data"].item()
        self.productos_filtrados = {}
        for index, item in self.data_products.items():
            if self.find(item[:5],termino_busqueda):
                self.productos_filtrados[index] = item
        self.actualizar_tree_productos()
            

    def find(self, lista, search):
        for i, element in enumerate(lista):
            if search.lower() in element.lower(): return True
        return False

    # ------------- Carrito
    def agregar_al_carrito(self, event=None):
        seleccion = self.tree.index(self.tree.selection()) + 1

        if seleccion:
            index = list(self.productos_filtrados.keys())[seleccion - 1]
            
            # Cantidad
            if index in self.carrito:
                self.carrito[index]['Cantidad'] += 1
            else:
                self.carrito[index] = {'Cantidad': 1}
            # Descuento
            self.carrito[index]["Porcentaje_Descuento"] = 0.0
            self.actualizar_importe(index)
            self.actualizar_tree_carrito()
    
    def actualizar_importe(self,index, item =""):
        Precio = float(self.data_products[index][self.index_precio])
        P_desc = self.carrito[index]["Porcentaje_Descuento"]
        Cantidad = self.carrito[index]['Cantidad']
        Descuento = round((Precio * P_desc) * Cantidad)
        
        self.carrito[index]["Descuento"] = Descuento
        self.carrito[index]["Importe"] = Precio * Cantidad - Descuento
        if item:
            self.tree_carrito.set(item=item, column="Cantidad", value=self.carrito[index]["Cantidad"])
            self.tree_carrito.set(item=item, column="Descuento", value=f'{self.carrito[index]["Descuento"]:4.2f}')
            self.tree_carrito.set(item=item, column="Importe", value= f'$ {self.carrito[index]["Importe"]:4.2f}')
            self.actualizar_totales()
            
        

    def actualizar_tree_carrito(self):
        # Elimina los elementos del carrito
        for item in self.tree_carrito.get_children():
                self.tree_carrito.delete(item)
        # Actualiza el carrito

        for index,item in self.carrito.items():
            product = self.data_products[index]
            self.tree_carrito.insert('', 'end', text=index, values=(f"{product[2]} ({product[5]})" , item["Cantidad"],f"{self.carrito[index]['Descuento']:4.2f}" , f"$ {self.carrito[index]['Importe']:4.2f}"))
        self.actualizar_totales()

    def actualizar_totales(self):
        self.Total = 0
        for index,item in self.carrito.items():
            self.Total += item["Importe"]
        self.etiqueta_total.configure(text=f'$ {self.Total:4.2f}')
        self.etiqueta_subtotal.configure(text = f"$ {self.Total/1.16:4.2f}")
        self.etiqueta_IVA.configure(text = f"$ {(self.Total/1.16)*0.16:4.2f}")


    def agregar_producto(self):
        if self.carrito:
            item = self.tree_carrito.selection()
            seleccion = self.tree_carrito.index(item)
            index = list(self.carrito.keys())[seleccion]
            self.carrito[index]["Cantidad"] += 1
            self.actualizar_importe(index = index, item = item)
            
    def descuento_producto(self):
        if self.carrito:
            
            def calcula_descuento(event = None):
                try:
                    desc = float(entry_descuento_p.get()) / 100
                    descuento = round(precio * desc)
                    label_descuento_val.configure(text=f"$ {descuento:4.2f}")
                    label_importe_val.configure(text=f"$ {precio - descuento:4.2f}")
                except:
                    label_descuento_val.configure(text=f" Error ")
                    label_importe_val.configure(text=f" Error ")
            
            def aplicar_descuento():
                try:
                    desc = float(entry_descuento_p.get()) / 100
                    self.carrito[index]["Porcentaje_Descuento"] = desc
                    self.actualizar_importe(index)
                    self.actualizar_tree_carrito()
                    Window.destroy()
                except:
                    pass
                
            item = self.tree_carrito.selection()
            seleccion = self.tree_carrito.index(item)
            index = list(self.carrito.keys())[seleccion]
            
            product = self.data_products[index]
            
            nombre = f"{product[2]} ({product[5]})"
            precio = product[self.index_precio]
            
            Window = tk.Toplevel(self.root)
            Window.title("Clientes")

            window_height = int(self.screen_height*0.2); window_width = int(self.screen_width*0.3)
            x_cordinate = int((self.screen_width/2) - (window_width/2));y_cordinate = int((self.screen_height*0.9/2) - (window_height/2))
            Window.geometry("{}x{}+{}+{}".format(window_width, window_height, x_cordinate, y_cordinate))
            
            label_nombre = tk.Label(Window, text= nombre, font = ("Arial", 12))
            places = [0.1,0.05,0.8,0.15]
            label_nombre.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
            
            label_precio = tk.Label(Window, text= "Precio :", font = ("Arial", 12), anchor='w')
            places = [0.1,0.2,0.25,0.15]
            label_precio.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
            
            label_precio_valor = tk.Label(Window, text= f"$ {precio:4.2f}", font = ("Arial", 12), anchor='e')
            places = [0.65,0.2,0.25,0.15]
            label_precio_valor.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
            
            label_descuento_p = tk.Label(Window, text= "Descuento % :", font = ("Arial", 12), anchor='w')
            places = [0.1,0.35,0.25,0.15]
            label_descuento_p.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
            
            entry_descuento_p = tk.Entry(Window, font = ("Arial", 12), justify=tk.RIGHT)
            places = [0.65,0.35,0.25,0.15]
            entry_descuento_p.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
            entry_descuento_p.bind("<KeyRelease>", calcula_descuento)
            
            label_descuento = tk.Label(Window, text= "Descuento :", font = ("Arial", 12), anchor='w')
            places = [0.1,0.5,0.25,0.15]
            label_descuento.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
            
            label_importe = tk.Label(Window, text= "Importe :", font = ("Arial", 12), anchor='w')
            places = [0.1,0.65,0.25,0.15]
            label_importe.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
            
            label_descuento_val = tk.Label(Window, text= f"$ {0:4.2f}", font = ("Arial", 12), anchor='e')
            places = [0.65,0.5,0.25,0.15]
            label_descuento_val.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
            
            label_importe_val = tk.Label(Window, text= f"$ {precio:4.2f}", font = ("Arial", 12), anchor='e')
            places = [0.65,0.65,0.25,0.15]
            label_importe_val.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
    
            button_descuento = tk.Button(Window, text=" Aplicar ", command=aplicar_descuento)
            places = [0.65,0.8,0.15,0.15]
            button_descuento.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])


    def quitar_producto(self):
        if self.carrito:
            item = self.tree_carrito.selection()
            seleccion = self.tree_carrito.index(item)
            index = list(self.carrito.keys())[seleccion]
            if self.carrito[index]["Cantidad"] > 1:
                self.carrito[index]["Cantidad"] -= 1
                self.actualizar_importe(index=index, item=item)
            else:
                self.tree_carrito.delete(item)
                self.carrito.pop(index)
                self.actualizar_totales()
    
    def client_Window(self):

        clientWindow = tk.Toplevel(self.root)
        clientWindow.title("Clientes")

        window_height = int(self.screen_height*0.35); window_width = int(self.screen_width*0.3)
        x_cordinate = int((self.screen_width/2) - (window_width/2));y_cordinate = int((self.screen_height*0.9/2) - (window_height/2))
        clientWindow.geometry("{}x{}+{}+{}".format(window_width, window_height, x_cordinate, y_cordinate))

        tree_cliente = ttk.Treeview(clientWindow, column=("Cliente", "Celular"), show='headings', height=15)
        places = [0.05,0.05,0.9,0.9]
        tree_cliente.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
        tree_cliente.column("# 1", anchor=tk.CENTER, width=int(window_width*0.6))
        tree_cliente.heading("# 1", text="Cliente")
        tree_cliente.column("# 2", anchor=tk.CENTER, width=int(window_width*0.3))
        tree_cliente.heading("# 2", text="Celular")

        for cliente, item in self.data_clients.items():
            tree_cliente.insert('', 'end', text=cliente, values=(f"{cliente}" , item["cel"]))

        # seleccion = self.tree.index(self.tree.selection()) + 1

        def modificar_cliente(event = None):
            seleccion = tree_cliente.index(tree_cliente.selection()) + 1
            if seleccion:
                nombre_cliente = list(self.data_clients.keys())[seleccion - 1]
                self.boton_cliente.configure(text=f"{nombre_cliente}")
                self.cliente = nombre_cliente

                clientWindow.destroy()
                clientWindow.update()

        tree_cliente.bind("<Double-Button-1>", modificar_cliente)


    def ajusta(self,i):
        i = str(i)
        if len(i) < 2: i = "0"+i
        return i
    
    def order_id(self):
        date = datetime.now()
        def ajusta(i, size = 2):
            i = str(i)
            if len(i)<size: 
                    for n in range(size - len(i)): i = "0"+i
            else:
                    i = i[-size:]
            return i
        id = f"{ajusta(date.year)}{ajusta(date.month)}{ajusta(date.day)}{ajusta(date.hour)}{ajusta(date.minute)}{ajusta(date.second)}"
        return id
    
    def actualiza_data(self):
        for index,item in self.carrito.items():
            self.data_products[index][8] -= item["Cantidad"]
        np.savez(self.path_data_products, data = self.data_products)
            
    def pagar(self):
        self.cobro_efectivo = 0
        if self.carrito:
            Total = self.Total
            def efectivo():
                check_tarjeta.deselect()
                self.metodo_pago = "Efectivo"
                def calcula_cambio(event=None):
                    try:
                        recibido = float(entry_cambio.get())
                        cambio = recibido - Total
                        label_cambio.configure(text=f"$ {cambio}")
                    except:
                        label_cambio.configure(text=f"$ 0.00")

                label_recibido = tk.Label(payWindow, text=" Recibido :", font = ("Arial", 14), anchor='w')
                places = [0.1,0.3,0.30,0.1]
                label_recibido.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])

                entry_cambio = tk.Entry(payWindow, justify=tk.RIGHT, font=("Arial", 14))
                places = [0.5,0.275,0.30,0.15]
                entry_cambio.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
                entry_cambio.bind("<KeyRelease>", calcula_cambio)

                label_cambio_name = tk.Label(payWindow, text=" Cambio :", font = ("Arial", 14), anchor='w')
                places = [0.1,0.5,0.30,0.1]
                label_cambio_name.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])

                label_cambio = tk.Label(payWindow, text="$ 0.00", font = ("Arial", 14), anchor='e')
                places = [0.5,0.5,0.30,0.1]
                label_cambio.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])

                buttom_cobro_realizado = tk.Button(payWindow, text=" Cobro realizado ", font = ("Arial", 14), command=venta_realizada)
                places = [0.15,0.7,0.7,0.2]
                buttom_cobro_realizado.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])
                self.cobro_efectivo = self.Total

            def tarjeta():
                check_efectivo.deselect()
                self.metodo_pago = "Tarjeta"
                buttom_cobro_realizado = tk.Button(payWindow, text=" Cobro realizado ", font = ("Arial", 14), command=venta_realizada)
                places = [0.15,0.7,0.7,0.2]
                buttom_cobro_realizado.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])

            def venta_realizada():
                payWindow.destroy()
                time = datetime.now()
                self.data_state['efectivo'] += self.cobro_efectivo
                self.data_orders[self.order_id()] = {"Cliente": self.cliente,
                                                     "Vendedor": self.usuario,
                                                     "Fecha": f"{self.ajusta(time.day)}/{self.ajusta(time.month)}/{time.year}",
                                                     "Hora": f"{self.ajusta(time.hour)}:{self.ajusta(time.minute)}:{self.ajusta(time.second)}",
                                                     "Metodo_pago": self.metodo_pago,
                                                     "Productos": self.carrito,
                                                     "Importe_total": self.Total}
                self.actualiza_data()
                # self.orders[self.order_id()] = {"Cliente":self.cliente,"Productos": self.carrito}
                
                np.savez(self.path_data_state,data = self.data_state)
                np.savez(self.path_data_orders, data = self.data_orders)
                
                self.carrito = {}
                self.opcion_punto_venta()

            payWindow = tk.Toplevel(self.root)
            payWindow.title("Metodo de pago")

            window_height = int(self.screen_height*0.25); window_width = int(self.screen_width*0.2)
            x_cordinate = int((self.screen_width/2) - (window_width/2));y_cordinate = int((self.screen_height*0.9/2) - (window_height/2))
            payWindow.geometry("{}x{}+{}+{}".format(window_width, window_height, x_cordinate, y_cordinate))

            var1 = tk.IntVar()
            check_efectivo = tk.Checkbutton(payWindow, text='Efectivo',variable=var1, onvalue=1, offvalue=0, command=efectivo, font=("Arial",12))
            places = [0.1,0.1,0.30,0.1]
            check_efectivo.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])

            var2 = tk.IntVar()
            check_tarjeta = tk.Checkbutton(payWindow, text='Tarjeta',variable=var2, onvalue=1, offvalue=0, command=tarjeta, font=("Arial",12))
            places = [0.5,0.1,0.30,0.1]
            check_tarjeta.place(x=window_width*places[0] ,y = window_height*places[1], width=window_width*places[2], height=window_height*places[3])


if __name__ == "__main__":
    root = tk.Tk()
    app = PuntoDeVenta(root)
    root.mainloop()



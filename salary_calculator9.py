import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import sqlite3
from datetime import datetime
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from tkcalendar import Calendar  # Установите: pip install tkcalendar

class SalaryCalculatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Система расчёта зарплаты")
        self.root.geometry("1100x750")
        self.root.resizable(True, True)

        # Инициализация базы данных
        self.init_database()

        # Загрузка сотрудников
        self.employee_map = {}  # fio -> (id, position, email, warehouse, salary)
        self.load_employees()

        # Создание вкладок
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Вкладка расчёта
        self.create_calculation_tab()

        # Вкладка архива
        self.create_archive_tab()

        # Вкладка управления сотрудниками
        self.create_employee_management_tab()

        # Вкладка календарь
        self.create_calendar_tab()

    def init_database(self):
        conn = sqlite3.connect('employees.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fio TEXT NOT NULL,
                position TEXT,
                email TEXT,
                warehouse TEXT,
                salary REAL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS salary_archive (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                fio TEXT,
                position TEXT,
                warehouse TEXT,
                base_salary REAL,
                fixed_bonus REAL,
                feoktistov_bonus REAL,
                overtime REAL,
                deduction_defect REAL,
                deduction_absent REAL,
                total REAL,
                calc_date TEXT,
                pdf_path TEXT,
                FOREIGN KEY (employee_id) REFERENCES employees (id)
            )
        ''')
        conn.commit()
        conn.close()

    def load_employees(self):
        conn = sqlite3.connect('employees.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, fio, position, email, warehouse, salary FROM employees")
        self.employee_map.clear()
        for row in cursor.fetchall():
            emp_id, fio, position, email, warehouse, salary = row
            self.employee_map[fio] = (emp_id, position, email, warehouse, salary)
        conn.close()

    def create_calculation_tab(self):
        calc_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(calc_frame, text="Расчёт зарплаты")

        # Сотрудник
        ttk.Label(calc_frame, text="ФИО сотрудника:", font=("Arial", 11)).grid(row=0, column=0, sticky='w', pady=5)
        self.combo_employee = ttk.Combobox(calc_frame, values=list(self.employee_map.keys()), state="readonly", width=80)
        self.combo_employee.grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))
        self.combo_employee.bind("<<ComboboxSelected>>", self.on_employee_select)

        # Окладная ставка (автоподстановка)
        ttk.Label(calc_frame, text="Окладная ставка (руб.):", font=("Arial", 11)).grid(row=1, column=0, sticky='w', pady=5)
        self.entry_base_salary = ttk.Entry(calc_frame, width=20)
        self.entry_base_salary.grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))
        self.entry_base_salary.bind("<FocusOut>", self.validate_salary)

        # Фиксированная премия
        ttk.Label(calc_frame, text="Фиксированная премия (руб.):", font=("Arial", 11)).grid(row=2, column=0, sticky='w', pady=5)
        self.entry_fixed_bonus = ttk.Entry(calc_frame, width=20)
        self.entry_fixed_bonus.grid(row=2, column=1, sticky='w', pady=5, padx=(10, 0))

        # Премия от Феоктистова
        ttk.Label(calc_frame, text="Премия от Феоктистова (руб.):", font=("Arial", 11)).grid(row=3, column=0, sticky='w', pady=5)
        self.entry_feoktistov_bonus = ttk.Entry(calc_frame, width=20)
        self.entry_feoktistov_bonus.grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))

        # Сверхурочные
        ttk.Label(calc_frame, text="Сверхурочные (руб.):", font=("Arial", 11)).grid(row=4, column=0, sticky='w', pady=5)
        self.entry_overtime = ttk.Entry(calc_frame, width=20)
        self.entry_overtime.grid(row=4, column=1, sticky='w', pady=5, padx=(10, 0))

        # Вычеты
        ttk.Label(calc_frame, text="Вычет за недостачу/пересорт (руб.):", font=("Arial", 11)).grid(row=5, column=0, sticky='w', pady=5)
        self.entry_deduction_defect = ttk.Entry(calc_frame, width=20)
        self.entry_deduction_defect.grid(row=5, column=1, sticky='w', pady=5, padx=(10, 0))

        ttk.Label(calc_frame, text="Вычет за дни Б/С (руб.):", font=("Arial", 11)).grid(row=6, column=0, sticky='w', pady=5)
        self.entry_deduction_absent = ttk.Entry(calc_frame, width=20)
        self.entry_deduction_absent.grid(row=6, column=1, sticky='w', pady=5, padx=(10, 0))

        # Дата расчёта (из календаря)
        ttk.Label(calc_frame, text="Дата расчёта:", font=("Arial", 11)).grid(row=7, column=0, sticky='w', pady=5)
        self.entry_calc_date = ttk.Entry(calc_frame, width=20)
        self.entry_calc_date.grid(row=7, column=1, sticky='w', pady=5, padx=(10, 0))
        self.entry_calc_date.insert(0, datetime.now().strftime("%d.%m.%Y"))
       

        # Кнопка расчёта
        btn_calc = ttk.Button(calc_frame, text="🔄 Рассчитать", command=self.calculate_salary)
        btn_calc.grid(row=8, column=0, columnspan=2, pady=15)

        # Итог
        self.label_total = ttk.Label(calc_frame, text="Итого: 0.00 руб.", font=("Arial", 14, "bold"), foreground="darkgreen")
        self.label_total.grid(row=9, column=0, columnspan=2, pady=10)

        # Кнопки действий
        btn_save = ttk.Button(calc_frame, text="💾 Сохранить в архив", command=self.save_to_archive)
        btn_save.grid(row=10, column=0, pady=10, sticky='e', padx=(0, 10))

        btn_print = ttk.Button(calc_frame, text="🖨 Печать", command=self.print_salary_receipt, style="Print.TButton")
        btn_print.grid(row=10, column=1, pady=10, sticky='w', padx=(10, 0))

        btn_email = ttk.Button(calc_frame, text="✉ Отправить на email", command=self.send_salary_by_email, style="Email.TButton")
        btn_email.grid(row=10, column=2, pady=10, sticky='w', padx=(10, 0))

        # Стили
        style = ttk.Style()
        style.configure("Print.TButton", foreground="darkgreen", font=("Arial", 11, "bold"))
        style.configure("Email.TButton", foreground="darkblue", font=("Arial", 11, "bold"))

    def on_employee_select(self, event):
        selected = self.combo_employee.get()
        if selected in self.employee_map:
            emp_id, position, email, warehouse, salary = self.employee_map[selected]
            # Автоподстановка оклада
            self.entry_base_salary.delete(0, tk.END)
            self.entry_base_salary.insert(0, f"{salary:.2f}" if salary else "")

            # Очистить остальные поля
            self.entry_fixed_bonus.delete(0, tk.END)
            self.entry_feoktistov_bonus.delete(0, tk.END)
            self.entry_overtime.delete(0, tk.END)
            self.entry_deduction_defect.delete(0, tk.END)
            self.entry_deduction_absent.delete(0, tk.END)
            self.label_total.config(text="Итого: 0.00 руб.")

    def validate_salary(self, event=None):
        try:
            val = self.entry_base_salary.get().strip()
            if val:
                float(val)
        except ValueError:
            messagebox.showwarning("Неверный формат", "Оклад должен быть числом.")

    def calculate_salary(self):
        try:
            base_salary = float(self.entry_base_salary.get() or 0)
            fixed_bonus = float(self.entry_fixed_bonus.get() or 0)
            feoktistov_bonus = float(self.entry_feoktistov_bonus.get() or 0)
            overtime = float(self.entry_overtime.get() or 0)
            deduction_defect = float(self.entry_deduction_defect.get() or 0)
            deduction_absent = float(self.entry_deduction_absent.get() or 0)

            total = base_salary + fixed_bonus + feoktistov_bonus + overtime - deduction_defect - deduction_absent
            self.label_total.config(text=f"Итого: {total:,.2f} руб.".replace(',', ' '))
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректные числовые значения.")

    def print_salary_receipt(self):
        selected_employee = self.combo_employee.get()
        if not selected_employee:
            messagebox.showerror("Ошибка", "Выберите сотрудника.")
            return

        emp_data = self.employee_map.get(selected_employee)
        if not emp_data:
            messagebox.showerror("Ошибка", "Данные сотрудника не найдены.")
            return

        emp_id, position, email, warehouse, salary = emp_data

        try:
            base_salary = float(self.entry_base_salary.get() or 0)
            fixed_bonus = float(self.entry_fixed_bonus.get() or 0)
            feoktistov_bonus = float(self.entry_feoktistov_bonus.get() or 0)
            overtime = float(self.entry_overtime.get() or 0)
            deduction_defect = float(self.entry_deduction_defect.get() or 0)
            deduction_absent = float(self.entry_deduction_absent.get() or 0)

            total = base_salary + fixed_bonus + feoktistov_bonus + overtime - deduction_defect - deduction_absent
            calc_date = self.entry_calc_date.get() or datetime.now().strftime("%d.%m.%Y")

            # Регистрация шрифтов
            pdfmetrics.registerFont(TTFont('DejaVu', 'DejaVuSans.ttf'))
            pdfmetrics.registerFont(TTFont('DejaVuBold', 'DejaVuSans-Bold.ttf'))

            filename = f"Зарплата_{selected_employee.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

            doc = SimpleDocTemplate(filename, pagesize=A4,
                                    rightMargin=30, leftMargin=30,
                                    topMargin=30, bottomMargin=30)
            styles = getSampleStyleSheet()
            style_normal = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontName='DejaVu',
                fontSize=10,
                leading=14,
            )
            style_bold = ParagraphStyle(
                'CustomBold',
                parent=styles['Normal'],
                fontName='DejaVuBold',
                fontSize=12,
                leading=16,
                alignment=1,
            )

            story = []

            story.append(Paragraph("📄 РАСЧЁТ ЗАРАБОТНОЙ ПЛАТЫ", style_bold))
            story.append(Spacer(1, 12))

            data = [
                ["ФИО:", selected_employee],
                ["Должность:", position],
                ["Склад:", warehouse],
                ["ID сотрудника:", str(emp_id)],
                ["Дата расчёта:", calc_date],
            ]
            table = Table(data, colWidths=[120, 300])
            table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
            ]))
            story.append(table)
            story.append(Spacer(1, 20))

            salary_data = [
                ["Позиция", "Сумма (руб.)"],
                ["Окладная ставка", f"{base_salary:,.2f}".replace(',', ' ')],
                ["Фиксированная премия", f"{fixed_bonus:,.2f}".replace(',', ' ')],
                ["Премия от Феоктистова", f"{feoktistov_bonus:,.2f}".replace(',', ' ')],
                ["Сверхурочные", f"{overtime:,.2f}".replace(',', ' ')],
                ["Вычет за недостачу и пересорт", f"-{deduction_defect:,.2f}".replace(',', ' ')],
                ["Вычет за дни Б/С", f"-{deduction_absent:,.2f}".replace(',', ' ')],
                ["", ""],
                ["**ИТОГО**", f"**{total:,.2f}**".replace(',', ' ')],
            ]
            salary_table = Table(salary_data, colWidths=[300, 120])
            salary_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.lightyellow),
                ('BACKGROUND', (0, -1), (1, -1), colors.lightgreen),
                ('FONTNAME', (0, -1), (1, -1), 'DejaVuBold'),
                ('FONTSIZE', (0, -1), (1, -1), 12),
            ]))
            story.append(salary_table)
            story.append(Spacer(1, 20))
            story.append(Paragraph("С уважением, бухгалтерский отдел", style_normal))
            story.append(Paragraph("2026, ООО «Стройсистема»", style_normal))

            doc.build(story)

            # Открытие PDF
            os.startfile(filename)

        except Exception as e:
            messagebox.showerror("Ошибка генерации PDF", str(e))

    def send_salary_by_email(self):
        selected_employee = self.combo_employee.get()
        if not selected_employee:
            messagebox.showerror("Ошибка", "Выберите сотрудника для отправки.")
            return

        emp_data = self.employee_map.get(selected_employee)
        if not emp_data:
            messagebox.showerror("Ошибка", "Данные сотрудника не найдены.")
            return

        emp_id, position, email, warehouse, salary = emp_data
        if not email or "@" not in email:
            messagebox.showerror("Ошибка", f"У сотрудника {selected_employee} не указан корректный email.")
            return

        try:
            base_salary = float(self.entry_base_salary.get() or 0)
            fixed_bonus = float(self.entry_fixed_bonus.get() or 0)
            feoktistov_bonus = float(self.entry_feoktistov_bonus.get() or 0)
            overtime = float(self.entry_overtime.get() or 0)
            deduction_defect = float(self.entry_deduction_defect.get() or 0)
            deduction_absent = float(self.entry_deduction_absent.get() or 0)

            total = base_salary + fixed_bonus + feoktistov_bonus + overtime - deduction_defect - deduction_absent
            calc_date = self.entry_calc_date.get() or datetime.now().strftime("%d.%m.%Y")

            # Регистрация шрифтов
            pdfmetrics.registerFont(TTFont('DejaVu', 'DejaVuSans.ttf'))
            pdfmetrics.registerFont(TTFont('DejaVuBold', 'DejaVuSans-Bold.ttf'))

            filename = f"Зарплата_{selected_employee.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

            doc = SimpleDocTemplate(filename, pagesize=A4,
                                    rightMargin=30, leftMargin=30,
                                    topMargin=30, bottomMargin=30)
            styles = getSampleStyleSheet()
            style_normal = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontName='DejaVu',
                fontSize=10,
                leading=14,
            )
            style_bold = ParagraphStyle(
                'CustomBold',
                parent=styles['Normal'],
                fontName='DejaVuBold',
                fontSize=12,
                leading=16,
                alignment=1,
            )

            story = []

            story.append(Paragraph("📄 РАСЧЁТ ЗАРАБОТНОЙ ПЛАТЫ", style_bold))
            story.append(Spacer(1, 12))

            data = [
                ["ФИО:", selected_employee],
                ["Должность:", position],
                ["Склад:", warehouse],
                ["ID сотрудника:", str(emp_id)],
                ["Дата расчёта:", calc_date],
            ]
            table = Table(data, colWidths=[120, 300])
            table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
            ]))
            story.append(table)
            story.append(Spacer(1, 20))

            salary_data = [
                ["Позиция", "Сумма (руб.)"],
                ["Окладная ставка", f"{base_salary:,.2f}".replace(',', ' ')],
                ["Фиксированная премия", f"{fixed_bonus:,.2f}".replace(',', ' ')],
                ["Премия от Феоктистова", f"{feoktistov_bonus:,.2f}".replace(',', ' ')],
                ["Сверхурочные", f"{overtime:,.2f}".replace(',', ' ')],
                ["Вычет за недостачу и пересорт", f"-{deduction_defect:,.2f}".replace(',', ' ')],
                ["Вычет за дни Б/С", f"-{deduction_absent:,.2f}".replace(',', ' ')],
                ["", ""],
                ["**ИТОГО**", f"**{total:,.2f}**".replace(',', ' ')],
            ]
            salary_table = Table(salary_data, colWidths=[300, 120])
            salary_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.lightyellow),
                ('BACKGROUND', (0, -1), (1, -1), colors.lightgreen),
                ('FONTNAME', (0, -1), (1, -1), 'DejaVuBold'),
                ('FONTSIZE', (0, -1), (1, -1), 12),
            ]))
            story.append(salary_table)
            story.append(Spacer(1, 20))
            story.append(Paragraph("С уважением, бухгалтерский отдел", style_normal))
            story.append(Paragraph("2026, ООО «Стройсистема»", style_normal))

            doc.build(story)

            # Отправка через SMTP (Gmail)
            smtp_server = "smtp.gmail.com"
            smtp_port = 587
            sender_email = "your_company_account@gmail.com"   # ← ЗАМЕНИТЕ НА СВОЙ
            sender_password = "your_app_password"            # ← ЗАМЕНИТЕ НА APP PASSWORD

            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = email
            msg['Subject'] = f"📄 Расчёт заработной платы за {datetime.now().strftime('%B %Y')}"

            body = f"""
            Добрый день, {selected_employee}!

            Ваш расчёт заработной платы за {datetime.now().strftime('%B %Y')} прилагается в виде PDF-файла.

            Итоговая сумма: {total:,.2f} руб.
            Склад: {warehouse}

            С уважением,
            Бухгалтерия компании ООО«Стройсистема»
            """
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            with open(filename, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {filename}',
                )
                msg.attach(part)

            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            text = msg.as_string()
            server.sendmail(sender_email, email, text)
            server.quit()

            messagebox.showinfo("Успех", f"Чек отправлен на email: {email}\n\nФайл: {filename}")

        except Exception as e:
            messagebox.showerror("Ошибка отправки", f"Не удалось отправить письмо:\n{e}\n\n"
                                                    f"Проверьте:\n"
                                                    f"- Корректность email сотрудника\n"
                                                    f"- Настройки SMTP (логин/пароль)\n"
                                                    f"- Разрешение на 'Пароли приложений' в Google (если используете Gmail)")

    def save_to_archive(self):
        selected_employee = self.combo_employee.get()
        if not selected_employee:
            messagebox.showerror("Ошибка", "Выберите сотрудника.")
            return

        emp_data = self.employee_map.get(selected_employee)
        if not emp_data:
            messagebox.showerror("Ошибка", "Данные сотрудника не найдены.")
            return

        emp_id, position, email, warehouse, salary = emp_data

        try:
            base_salary = float(self.entry_base_salary.get() or 0)
            fixed_bonus = float(self.entry_fixed_bonus.get() or 0)
            feoktistov_bonus = float(self.entry_feoktistov_bonus.get() or 0)
            overtime = float(self.entry_overtime.get() or 0)
            deduction_defect = float(self.entry_deduction_defect.get() or 0)
            deduction_absent = float(self.entry_deduction_absent.get() or 0)

            total = base_salary + fixed_bonus + feoktistov_bonus + overtime - deduction_defect - deduction_absent
            calc_date = self.entry_calc_date.get() or datetime.now().strftime("%d.%m.%Y %H:%M")

            # Генерируем имя файла
            filename = f"Зарплата_{selected_employee.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

            # Сохраняем PDF
            pdfmetrics.registerFont(TTFont('DejaVu', 'DejaVuSans.ttf'))
            pdfmetrics.registerFont(TTFont('DejaVuBold', 'DejaVuSans-Bold.ttf'))

            doc = SimpleDocTemplate(filename, pagesize=A4,
                                    rightMargin=30, leftMargin=30,
                                    topMargin=30, bottomMargin=30)
            styles = getSampleStyleSheet()
            style_normal = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontName='DejaVu',
                fontSize=10,
                leading=14,
            )
            style_bold = ParagraphStyle(
                'CustomBold',
                parent=styles['Normal'],
                fontName='DejaVuBold',
                fontSize=12,
                leading=16,
                alignment=1,
            )

            story = []
            story.append(Paragraph("📄 РАСЧЁТ ЗАРАБОТНОЙ ПЛАТЫ", style_bold))
            story.append(Spacer(1, 12))

            data = [
                ["ФИО:", selected_employee],
                ["Должность:", position],
                ["Склад:", warehouse],
                ["ID сотрудника:", str(emp_id)],
                ["Дата расчёта:", calc_date],
            ]
            table = Table(data, colWidths=[120, 300])
            table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
            ]))
            story.append(table)
            story.append(Spacer(1, 20))

            salary_data = [
                ["Позиция", "Сумма (руб.)"],
                ["Окладная ставка", f"{base_salary:,.2f}".replace(',', ' ')],
                ["Фиксированная премия", f"{fixed_bonus:,.2f}".replace(',', ' ')],
                ["Премия от Феоктистова", f"{feoktistov_bonus:,.2f}".replace(',', ' ')],
                ["Сверхурочные", f"{overtime:,.2f}".replace(',', ' ')],
                ["Вычет за недостачу и пересорт", f"-{deduction_defect:,.2f}".replace(',', ' ')],
                ["Вычет за дни Б/С", f"-{deduction_absent:,.2f}".replace(',', ' ')],
                ["", ""],
                ["**ИТОГО**", f"**{total:,.2f}**".replace(',', ' ')],
            ]
            salary_table = Table(salary_data, colWidths=[300, 120])
            salary_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.lightyellow),
                ('BACKGROUND', (0, -1), (1, -1), colors.lightgreen),
                ('FONTNAME', (0, -1), (1, -1), 'DejaVuBold'),
                ('FONTSIZE', (0, -1), (1, -1), 12),
            ]))
            story.append(salary_table)
            story.append(Spacer(1, 20))
            story.append(Paragraph("С уважением, бухгалтерский отдел", style_normal))
            story.append(Paragraph("2026, ООО «Стройсистема»", style_normal))

            doc.build(story)

            # Сохраняем в архив базы данных
            conn = sqlite3.connect('employees.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO salary_archive (employee_id, fio, position, warehouse, base_salary, fixed_bonus, feoktistov_bonus, 
                overtime, deduction_defect, deduction_absent, total, calc_date, pdf_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (emp_id, selected_employee, position, warehouse, base_salary, fixed_bonus, feoktistov_bonus,
                  overtime, deduction_defect, deduction_absent, total, calc_date, filename))
            conn.commit()
            conn.close()

            messagebox.showinfo("Успех", f"Запись сохранена в архив.\nФайл: {filename}")

        except Exception as e:
            messagebox.showerror("Ошибка сохранения", str(e))

    def create_archive_tab(self):
        archive_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(archive_frame, text="Архив")

        # Таблица архива
        columns = ("id", "fio", "position", "warehouse", "total", "calc_date", "pdf_path")
        self.archive_tree = ttk.Treeview(archive_frame, columns=columns, show="headings", height=15)
        self.archive_tree.heading("id", text="ID")
        self.archive_tree.heading("fio", text="ФИО")
        self.archive_tree.heading("position", text="Должность")
        self.archive_tree.heading("warehouse", text="Склад")
        self.archive_tree.heading("total", text="Итого")
        self.archive_tree.heading("calc_date", text="Дата")
        self.archive_tree.heading("pdf_path", text="PDF")

        self.archive_tree.column("id", width=40)
        self.archive_tree.column("fio", width=150)
        self.archive_tree.column("position", width=120)
        self.archive_tree.column("warehouse", width=100)
        self.archive_tree.column("total", width=100)
        self.archive_tree.column("calc_date", width=150)
        self.archive_tree.column("pdf_path", width=200)

        scrollbar = ttk.Scrollbar(archive_frame, orient="vertical", command=self.archive_tree.yview)
        self.archive_tree.configure(yscroll=scrollbar.set)

        self.archive_tree.grid(row=0, column=0, sticky='nsew', pady=(0, 10))
        scrollbar.grid(row=0, column=1, sticky='ns', pady=(0, 10))

        btn_open = ttk.Button(archive_frame, text="📂 Открыть PDF", command=self.open_selected_pdf)
        btn_open.grid(row=1, column=0, sticky='w', pady=5)

        btn_delete = ttk.Button(archive_frame, text="🗑 Удалить запись", command=self.delete_selected_record)
        btn_delete.grid(row=1, column=0, sticky='e', pady=5)

        archive_frame.grid_columnconfigure(0, weight=1)
        archive_frame.grid_rowconfigure(0, weight=1)

        self.load_archive()

    def load_archive(self):
        for item in self.archive_tree.get_children():
            self.archive_tree.delete(item)

        conn = sqlite3.connect('employees.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT sa.id, sa.fio, sa.position, sa.warehouse, sa.total, sa.calc_date, sa.pdf_path
            FROM salary_archive sa
            ORDER BY sa.calc_date DESC
        ''')
        for row in cursor.fetchall():
            self.archive_tree.insert("", "end", values=row)
        conn.close()

    def open_selected_pdf(self):
        selected = self.archive_tree.selection()
        if not selected:
            messagebox.showwarning("Предупреждение", "Выберите запись.")
            return

        item = self.archive_tree.item(selected[0])
        pdf_path = item['values'][6]
        if not os.path.exists(pdf_path):
            messagebox.showerror("Ошибка", "Файл PDF не найден на диске.")
            return
        os.startfile(pdf_path)

    def delete_selected_record(self):
        selected = self.archive_tree.selection()
        if not selected:
            messagebox.showwarning("Предупреждение", "Выберите запись для удаления.")
            return

        if not messagebox.askyesno("Подтверждение", "Вы уверены, что хотите удалить эту запись?"):
            return

        item = self.archive_tree.item(selected[0])
        record_id = item['values'][0]

        conn = sqlite3.connect('employees.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM salary_archive WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()

        self.load_archive()
        messagebox.showinfo("Успех", "Запись удалена из архива.")

    def create_employee_management_tab(self):
        emp_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(emp_frame, text="Управление сотрудниками")

        # Форма добавления
        ttk.Label(emp_frame, text="ФИО:", font=("Arial", 11)).grid(row=0, column=0, sticky='w', pady=5)
        self.entry_new_fio = ttk.Entry(emp_frame, width=80)
        self.entry_new_fio.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(emp_frame, text="Должность:", font=("Arial", 11)).grid(row=1, column=0, sticky='w', pady=5)
        self.entry_new_position = ttk.Entry(emp_frame, width=80)
        self.entry_new_position.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(emp_frame, text="Email:", font=("Arial", 11)).grid(row=2, column=0, sticky='w', pady=5)
        self.entry_new_email = ttk.Entry(emp_frame, width=80)
        self.entry_new_email.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(emp_frame, text="Склад:", font=("Arial", 11)).grid(row=3, column=0, sticky='w', pady=5)
        self.entry_new_warehouse = ttk.Entry(emp_frame, width=30)
        self.entry_new_warehouse.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(emp_frame, text="Оклад (руб.):", font=("Arial", 11)).grid(row=4, column=0, sticky='w', pady=5)
        self.entry_new_salary = ttk.Entry(emp_frame, width=30)
        self.entry_new_salary.grid(row=4, column=1, pady=5, padx=(10, 0))

        btn_add = ttk.Button(emp_frame, text="➕ Добавить сотрудника", command=self.add_employee)
        btn_add.grid(row=5, column=0, columnspan=2, pady=15)

        # Список сотрудников
        columns_emp = ("id", "fio", "position", "email", "warehouse", "salary")
        self.emp_tree = ttk.Treeview(emp_frame, columns=columns_emp, show="headings", height=10)
        self.emp_tree.heading("id", text="ID")
        self.emp_tree.heading("fio", text="ФИО")
        self.emp_tree.heading("position", text="Должность")
        self.emp_tree.heading("email", text="Email")
        self.emp_tree.heading("warehouse", text="Склад")
        self.emp_tree.heading("salary", text="Оклад")

        self.emp_tree.column("id", width=40)
        self.emp_tree.column("fio", width=150)
        self.emp_tree.column("position", width=120)
        self.emp_tree.column("email", width=180)
        self.emp_tree.column("warehouse", width=100)
        self.emp_tree.column("salary", width=80)

        scrollbar_emp = ttk.Scrollbar(emp_frame, orient="vertical", command=self.emp_tree.yview)
        self.emp_tree.configure(yscroll=scrollbar_emp.set)

        self.emp_tree.grid(row=6, column=0, columnspan=2, sticky='nsew', pady=(10, 0))
        scrollbar_emp.grid(row=6, column=2, sticky='ns', pady=(10, 0))

        btn_delete_emp = ttk.Button(emp_frame, text="🗑 Удалить", command=self.delete_employee)
        btn_delete_emp.grid(row=7, column=0, sticky='w', pady=10)

        btn_refresh = ttk.Button(emp_frame, text="🔄 Обновить", command=self.refresh_employees)
        btn_refresh.grid(row=7, column=1, sticky='e', pady=10)

        # Двойной клик для редактирования
        self.emp_tree.bind("<Double-1>", self.on_employee_double_click)

        emp_frame.grid_columnconfigure(1, weight=1)
        emp_frame.grid_rowconfigure(6, weight=1)

        self.refresh_employees()

    def on_employee_double_click(self, event):
        selected = self.emp_tree.selection()
        if not selected:
            return

        item = self.emp_tree.item(selected[0])
        emp_id = item['values'][0]
        fio = item['values'][1]
        position = item['values'][2]
        email = item['values'][3]
        warehouse = item['values'][4]
        salary = item['values'][5]

        # Открываем форму редактирования
        new_fio = simpledialog.askstring("Редактирование", "ФИО:", initialvalue=fio)
        if new_fio is None: return

        new_position = simpledialog.askstring("Редактирование", "Должность:", initialvalue=position)
        if new_position is None: return

        new_email = simpledialog.askstring("Редактирование", "Email:", initialvalue=email)
        if new_email is None: return

        new_warehouse = simpledialog.askstring("Редактирование", "Склад:", initialvalue=warehouse)
        if new_warehouse is None: return

        new_salary = simpledialog.askstring("Редактирование", "Оклад (руб.):", initialvalue=str(salary))
        if new_salary is None: return

        try:
            new_salary = float(new_salary)
        except ValueError:
            messagebox.showerror("Ошибка", "Оклад должен быть числом.")
            return

        conn = sqlite3.connect('employees.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE employees SET fio=?, position=?, email=?, warehouse=?, salary=? WHERE id=?
        ''', (new_fio, new_position, new_email, new_warehouse, new_salary, emp_id))
        conn.commit()
        conn.close()

        self.load_employees()
        self.refresh_employees()
        self.combo_employee['values'] = list(self.employee_map.keys())
        messagebox.showinfo("Успех", "Сотрудник обновлён.")

    def add_employee(self):
        fio = self.entry_new_fio.get().strip()
        position = self.entry_new_position.get().strip()
        email = self.entry_new_email.get().strip()
        warehouse = self.entry_new_warehouse.get().strip()
        salary_str = self.entry_new_salary.get().strip()

        if not fio:
            messagebox.showerror("Ошибка", "Введите ФИО.")
            return

        try:
            salary = float(salary_str) if salary_str else 0.0
        except ValueError:
            messagebox.showerror("Ошибка", "Оклад должен быть числом.")
            return

        conn = sqlite3.connect('employees.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO employees (fio, position, email, warehouse, salary) VALUES (?, ?, ?, ?, ?)", 
                       (fio, position, email, warehouse, salary))
        conn.commit()
        conn.close()

        self.entry_new_fio.delete(0, tk.END)
        self.entry_new_position.delete(0, tk.END)
        self.entry_new_email.delete(0, tk.END)
        self.entry_new_warehouse.delete(0, tk.END)
        self.entry_new_salary.delete(0, tk.END)

        self.load_employees()
        self.refresh_employees()
        self.combo_employee['values'] = list(self.employee_map.keys())
        messagebox.showinfo("Успех", "Сотрудник добавлен.")

    def delete_employee(self):
        selected = self.emp_tree.selection()
        if not selected:
            messagebox.showwarning("Предупреждение", "Выберите сотрудника для удаления.")
            return

        item = self.emp_tree.item(selected[0])
        emp_id = item['values'][0]

        if not messagebox.askyesno("Подтверждение", "Удалить сотрудника? Все его записи в архиве останутся."):
            return

        conn = sqlite3.connect('employees.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
        conn.commit()
        conn.close()

        self.load_employees()
        self.refresh_employees()
        self.combo_employee['values'] = list(self.employee_map.keys())
        messagebox.showinfo("Успех", "Сотрудник удалён.")

    def refresh_employees(self):
        for item in self.emp_tree.get_children():
            self.emp_tree.delete(item)

        conn = sqlite3.connect('employees.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, fio, position, email, warehouse, salary FROM employees ORDER BY fio")
        for row in cursor.fetchall():
            self.emp_tree.insert("", "end", values=row)
        conn.close()

    def create_calendar_tab(self):
        cal_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(cal_frame, text="Календарь")

        # Календарь
        self.calendar = Calendar(cal_frame, selectmode='day', year=datetime.now().year, 
                                 month=datetime.now().month, day=datetime.now().day)
        self.calendar.grid(row=0, column=0, columnspan=2, pady=10)

    def select_date_from_calendar(self):
        selected_date = self.calendar.get_date()  # Формат: MM/DD/YYYY
        # Преобразуем в русский формат: DD.MM.YYYY
        try:
            dt = datetime.strptime(selected_date, "%m/%d/%Y")
            formatted_date = dt.strftime("%d.%m.%Y")
            self.label_calendar_date.config(text=f"Выбранная дата: {formatted_date}")

            # Если текущая вкладка — Расчёт зарплаты, обновляем поле даты
            if self.notebook.index("current") == 0:  # Индекс вкладки "Расчёт зарплаты"
                self.entry_calc_date.delete(0, tk.END)
                self.entry_calc_date.insert(0, formatted_date)

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обработать дату: {e}")

    def open_calendar(self):
        # Эта функция вызывается из вкладки "Расчёт зарплаты"
        # Она просто переключает на вкладку календарь
        self.notebook.select(3)  # Индекс вкладки "Календарь"
        # Можно также автоматически скопировать дату в поле расчёта
        selected_date = self.calendar.get_date()
        try:
            dt = datetime.strptime(selected_date, "%m/%d/%Y")
            formatted_date = dt.strftime("%d.%m.%Y")
            self.entry_calc_date.delete(0, tk.END)
            self.entry_calc_date.insert(0, formatted_date)
        except:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    app = SalaryCalculatorApp(root)
    root.mainloop()

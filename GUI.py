"""A small desktop portal for closed client invoices and PDF scanning."""

from __future__ import annotations

import re
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from tkinter import END, filedialog, messagebox
from tkinter import StringVar, Tk
from tkinter import ttk


NUMBER_PATTERN = re.compile(r"(?<!\d)\d{2,}(?!\d)")
INVOICE_WORDS = ("invoice", "invoices", "فاتورة", "فواتير")
QUOTATION_WORDS = ("quotation", "quote", "quotations", "عرض سعر", "كوتيشن")
CUSTOMER_NAME_PATTERN = re.compile(
    r"customer\s*name\s*:\s*([^\r\n]+)", re.IGNORECASE
)
TOTAL_AMOUNT_PATTERN = re.compile(
    r"total\s*amount\s*:\s*([^\r\n]+)", re.IGNORECASE
)


def read_pdf_text(pdf_path: Path) -> str:
    """Return text from a PDF using the optional pypdf package."""
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as error:
        raise RuntimeError(
            "قراءة ملفات PDF تحتاج إلى تثبيت الحزمة pypdf:\n"
            "python -m pip install pypdf"
        ) from error

    try:
        reader = PdfReader(str(pdf_path))
        pages_text = [(page.extract_text() or "") for page in reader.pages]
    except PdfReadError as error:
        raise RuntimeError(f"ملف PDF غير صالح أو محمي: {error}") from error
    return "\n".join(pages_text)


def classify_document(text: str) -> str:
    """Classify a document according to the words found in its name or text."""
    normalized_text = text.casefold()
    has_invoice = any(word in normalized_text for word in INVOICE_WORDS)
    has_quotation = any(word in normalized_text for word in QUOTATION_WORDS)

    if has_invoice and has_quotation:
        return "Invoice Quotation"
    if has_quotation:
        return "Quotation"
    return "Invoice"


def extract_document_numbers(text: str) -> list[str]:
    """Extract useful multi-digit identifiers while preserving their order."""
    numbers: list[str] = []
    for number in NUMBER_PATTERN.findall(text):
        if number not in numbers:
            numbers.append(number)
    return numbers


def extract_customer_name(text: str) -> str | None:
    """Extract the customer name written after the Customer Name label."""
    match = CUSTOMER_NAME_PATTERN.search(text)
    if not match:
        return None
    customer_name = " ".join(match.group(1).split())
    return customer_name or None


def extract_file_creation_month(pdf_path: Path) -> str:
    """Return the month in which Windows created the PDF file."""
    creation_time = pdf_path.stat().st_ctime
    return datetime.fromtimestamp(creation_time).strftime("%Y-%m (%B %Y)")


def extract_total_amount(text: str) -> str:
    """Extract the value written after the Total amount label."""
    match = TOTAL_AMOUNT_PATTERN.search(text)
    if not match:
        return "Unknown amount"
    total_amount = " ".join(match.group(1).split())
    return total_amount or "Unknown amount"


class InvoicePortal:
    def __init__(self, window: Tk) -> None:
        self.window = window
        self.window.title("Client Invoice Portal")
        self.window.geometry("1200x650")
        self.window.minsize(950, 500)

        self.folder_path = StringVar()
        self.document_type = StringVar(value="All")
        self.summary = StringVar(value="0 documents")
        self.invoice_count = StringVar(value="0")
        self.quotation_count = StringVar(value="0")
        self.pdf_paths: dict[str, Path] = {}
        self.row_order: list[str] = []

        self._configure_style()
        self._build_layout()

    def _configure_style(self) -> None:
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Subtitle.TLabel", foreground="#536174")
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    def _build_layout(self) -> None:
        main = ttk.Frame(self.window, padding=22)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(3, weight=1)

        ttk.Label(main, text="Client Invoice Portal", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            main,
            text="Add closed invoices and scan a folder to read PDF names and identifiers.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 18))

        form = ttk.LabelFrame(main, text="Scan closed client PDFs", padding=14)
        form.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="PDF folder").grid(row=0, column=0, padx=(0, 10), sticky="w")
        ttk.Entry(form, textvariable=self.folder_path).grid(
            row=0, column=1, sticky="ew"
        )
        ttk.Button(form, text="Browse", command=self.choose_folder).grid(
            row=0, column=2, padx=(8, 0)
        )
        ttk.Button(
            form,
            text="Scan PDFs",
            style="Accent.TButton",
            command=self.scan_folder,
        ).grid(row=0, column=3, padx=(8, 0))

        table_frame = ttk.Frame(main)
        table_frame.grid(row=3, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        columns = ("client", "file", "type", "numbers", "month", "amount", "status")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings")
        headings = {
            "client": "Client",
            "file": "PDF file",
            "type": "Document type",
            "numbers": "Invoice / inquiry numbers",
            "month": "Created month",
            "amount": "Total amount",
            "status": "Status",
        }
        widths = {
            "client": 150,
            "file": 250,
            "type": 150,
            "numbers": 220,
            "month": 110,
            "amount": 140,
            "status": 100,
        }
        for column in columns:
            self.table.heading(column, text=headings[column])
            self.table.column(column, width=widths[column], anchor="w")
        self.table.grid(row=0, column=0, sticky="nsew")
        self.table.bind("<Double-1>", self.open_selected_pdf)
        self.table.bind("<Return>", self.open_selected_pdf)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scrollbar.set)

        statistics = ttk.LabelFrame(main, text="Statistics", padding=12)
        statistics.grid(row=3, column=1, sticky="nsew", padx=(14, 0))
        statistics.columnconfigure(0, weight=1)
        ttk.Label(statistics, text="Invoices", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(statistics, textvariable=self.invoice_count, font=("Segoe UI", 22, "bold")).grid(
            row=1, column=0, sticky="w", pady=(0, 12)
        )
        ttk.Label(statistics, text="Quotations", font=("Segoe UI", 11, "bold")).grid(
            row=2, column=0, sticky="w"
        )
        ttk.Label(statistics, textvariable=self.quotation_count, font=("Segoe UI", 22, "bold")).grid(
            row=3, column=0, sticky="w", pady=(0, 14)
        )
        ttk.Label(statistics, text="Invoices by creation month", font=("Segoe UI", 11, "bold")).grid(
            row=4, column=0, sticky="w", pady=(0, 6)
        )
        self.month_table = ttk.Treeview(
            statistics, columns=("month", "count"), show="headings", height=10
        )
        self.month_table.heading("month", text="Month")
        self.month_table.heading("count", text="Count")
        self.month_table.column("month", width=110, anchor="w")
        self.month_table.column("count", width=60, anchor="center")
        self.month_table.grid(row=5, column=0, sticky="nsew")
        self.month_table.bind("<ButtonRelease-1>", self.filter_by_month)
        statistics.rowconfigure(5, weight=1)

        footer = ttk.Frame(main)
        footer.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        ttk.Label(footer, textvariable=self.summary).pack(side="left")
        ttk.Button(footer, text="Show all", command=self.show_all_documents).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(footer, text="Clear list", command=self.clear_list).pack(side="right")

    def choose_folder(self) -> None:
        selected_folder = filedialog.askdirectory(title="Select PDF folder")
        if selected_folder:
            self.folder_path.set(selected_folder)

    def scan_folder(self) -> None:
        folder = Path(self.folder_path.get().strip())
        if not folder.is_dir():
            messagebox.showerror("Invalid folder", "Select an existing PDF folder.")
            return

        pdf_files = sorted(folder.glob("*.pdf"))
        if not pdf_files:
            messagebox.showinfo("No PDFs", "No PDF files were found in this folder.")
            return

        errors: list[str] = []
        added = 0
        for pdf_path in pdf_files:
            try:
                pdf_text = read_pdf_text(pdf_path)
                searchable_text = f"{pdf_path.stem}\n{pdf_text}"
                client = extract_customer_name(pdf_text)
                if not client:
                    raise ValueError("Customer Name: was not found in the PDF")
                document_type = classify_document(searchable_text)
                numbers = extract_document_numbers(searchable_text)
                creation_month = extract_file_creation_month(pdf_path)
            except (OSError, RuntimeError, ValueError) as error:
                errors.append(f"{pdf_path.name}: {error}")
                continue

            item_id = self.table.insert(
                "",
                END,
                values=(
                    client,
                    pdf_path.name,
                    document_type,
                    ", ".join(numbers) if numbers else "No numbers found",
                    creation_month,
                    extract_total_amount(pdf_text),
                    "Closed",
                ),
            )
            self.pdf_paths[item_id] = pdf_path
            self.row_order.append(item_id)
            added += 1

        self._refresh_statistics()
        self.summary.set(f"{len(self.row_order)} documents")
        if errors:
            messagebox.showwarning(
                "Some PDFs could not be read",
                f"Added {added} document(s).\n\n" + "\n".join(errors),
            )
        elif added:
            messagebox.showinfo("Scan complete", f"Added {added} document(s).")

    def clear_list(self) -> None:
        for item in self.row_order:
            self.table.delete(item)
        self.pdf_paths.clear()
        self.row_order.clear()
        self._refresh_statistics()
        self.summary.set("0 documents")

    def filter_by_month(self, _event: object | None = None) -> None:
        selected_items = self.month_table.selection()
        if not selected_items:
            return
        selected_month = str(self.month_table.item(selected_items[0], "values")[0])
        visible_count = 0
        for item_id in self.row_order:
            values = self.table.item(item_id, "values")
            if str(values[4]) == selected_month:
                self.table.reattach(item_id, "", "end")
                visible_count += 1
            else:
                self.table.detach(item_id)
        self.summary.set(f"{visible_count} documents - {selected_month}")

    def show_all_documents(self) -> None:
        for position, item_id in enumerate(self.row_order):
            self.table.reattach(item_id, "", position)
        self.summary.set(f"{len(self.row_order)} documents")

    def open_selected_pdf(self, _event: object | None = None) -> None:
        selected_items = self.table.selection()
        if not selected_items:
            return

        pdf_path = self.pdf_paths.get(selected_items[0])
        if not pdf_path:
            messagebox.showerror("File not found", "The PDF path for this row is unavailable.")
            return
        if not pdf_path.is_file():
            messagebox.showerror("File not found", f"Could not find:\n{pdf_path}")
            return

        try:
            os.startfile(str(pdf_path))
        except OSError as error:
            messagebox.showerror("Could not open PDF", f"{pdf_path.name}\n\n{error}")

    def _refresh_statistics(self) -> None:
        invoice_total = 0
        quotation_total = 0
        monthly_invoices: Counter[str] = Counter()
        for item in self.row_order:
            values = self.table.item(item, "values")
            document_type = str(values[2])
            month = str(values[4])
            if "Invoice" in document_type:
                invoice_total += 1
                monthly_invoices[month] += 1
            if "Quotation" in document_type:
                quotation_total += 1

        self.invoice_count.set(str(invoice_total))
        self.quotation_count.set(str(quotation_total))
        for item in self.month_table.get_children():
            self.month_table.delete(item)
        for month, count in sorted(monthly_invoices.items()):
            self.month_table.insert("", END, values=(month, count))


def main() -> None:
    window = Tk()
    InvoicePortal(window)
    window.mainloop()


if __name__ == "__main__":
    main()

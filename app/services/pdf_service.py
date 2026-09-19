import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.models.payroll import PayrollRecord


class PDFService:

    @staticmethod
    def generate_payslip_pdf(record: PayrollRecord) -> io.BytesIO:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleStyle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            alignment=1,
            textColor=colors.HexColor("#1A365D"),
        )
        subtitle_style = ParagraphStyle(
            "SubTitleStyle",
            parent=styles["Normal"],
            fontSize=11,
            leading=15,
            alignment=1,
            textColor=colors.HexColor("#4A5568"),
        )
        label_style = ParagraphStyle(
            "LabelStyle",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#2D3748"),
        )
        bold_label = ParagraphStyle(
            "BoldLabel",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#1A202C"),
        )

        story = []

        # 1. Company Header
        story.append(Paragraph("HR ENTERPRISE SYSTEMS", title_style))
        story.append(Paragraph(f"PAYSLIP FOR {record.year} - {record.month:02d}", subtitle_style))
        story.append(Spacer(1, 15))

        # 2. Employee Info Table
        emp = record.employee
        emp_info = [
            [
                Paragraph("<b>Employee Name:</b>", label_style),
                Paragraph(f"{emp.first_name} {emp.last_name}", bold_label),
                Paragraph("<b>Employee Code:</b>", label_style),
                Paragraph(emp.employee_code, bold_label),
            ],
            [
                Paragraph("<b>Designation:</b>", label_style),
                Paragraph(emp.designation or "N/A", bold_label),
                Paragraph("<b>Date of Joining:</b>", label_style),
                Paragraph(str(emp.date_of_joining) if emp.date_of_joining else "N/A", bold_label),
            ],
            [
                Paragraph("<b>Payment Status:</b>", label_style),
                Paragraph(record.status.upper(), bold_label),
                Paragraph("<b>Payment Date:</b>", label_style),
                Paragraph(str(record.payment_date) if record.payment_date else "N/A", bold_label),
            ],
        ]

        t_emp = Table(emp_info, colWidths=[1.5 * inch, 2.0 * inch, 1.5 * inch, 2.0 * inch])
        t_emp.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t_emp)
        story.append(Spacer(1, 12))

        # 3. Attendance Breakdown Table
        att_info = [
            ["Total Days", "Present Days", "Half Days", "Paid Leaves", "LOP / Unpaid Days", "Weekends"],
            [
                str(record.total_days_in_month),
                f"{float(record.present_days):.1f}",
                f"{float(record.half_days):.1f}",
                f"{float(record.paid_leave_days):.1f}",
                f"{float(record.unpaid_leave_days):.1f}",
                str(record.weekend_days),
            ],
        ]
        t_att = Table(att_info, colWidths=[1.15 * inch] * 6)
        t_att.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#2D3748")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t_att)
        story.append(Spacer(1, 12))

        # 4. Earnings & Deductions Ledger Table
        ledger_data = [
            ["Earnings", "Amount (INR)", "Deductions", "Amount (INR)"],
            ["Gross Salary", f"{float(record.gross_salary):,.2f}", "LOP Deduction", f"{float(record.lop_deduction):,.2f}"],
            ["", "", "Provident Fund (PF)", f"{float(record.pf_deduction):,.2f}"],
            ["", "", "Professional Tax (PT)", f"{float(record.professional_tax):,.2f}"],
            ["Total Earnings", f"{float(record.gross_salary):,.2f}", "Total Deductions", f"{float(record.total_deductions):,.2f}"],
        ]

        t_ledger = Table(ledger_data, colWidths=[2.2 * inch, 1.3 * inch, 2.2 * inch, 1.3 * inch])
        t_ledger.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#EBF8FF")),
            ("BACKGROUND", (2, 0), (3, 0), colors.HexColor("#FFF5F5")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("ALIGN", (3, 1), (3, -1), "RIGHT"),
            ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#CBD5E0")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t_ledger)
        story.append(Spacer(1, 12))

        # 5. Net Take-Home Highlight
        net_data = [
            [Paragraph("<b>NET TAKE-HOME SALARY:</b>", bold_label), f"INR {float(record.net_salary):,.2f}"]
        ]
        t_net = Table(net_data, colWidths=[4.5 * inch, 2.5 * inch])
        t_net.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#2B6CB0")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(t_net)

        doc.build(story)
        buffer.seek(0)
        return buffer
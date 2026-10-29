import os
import csv
import time
from typing import List, Dict, Any

class EcommerceExporter:
    """电商爆款商品数据导出器 (支持 Excel .xlsx 样式排版与 CSV 兜底)"""

    def __init__(self, output_dir: str = "materials/ecommerce_products"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def export_excel(self, products: List[Dict[str, Any]], filename: str = "爆款选品汇总.xlsx") -> str:
        """导出为 Excel 文件"""
        filepath = os.path.join(self.output_dir, filename)

        headers = [
            "平台", "商品名称", "价格", "销量/已拼", "评分/好评率", 
            "店铺名称", "商品链接", "本地素材文件夹", "抓取时间"
        ]

        rows = []
        for p in products:
            rows.append([
                p.get("platform_name", ""),
                p.get("title", ""),
                p.get("price", 0.0),
                p.get("sales", 0),
                p.get("rating", ""),
                p.get("store_name", ""),
                p.get("url", ""),
                p.get("material_dir", ""),
                p.get("created_at", time.strftime("%Y-%m-%d %H:%M:%S"))
            ])

        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "爆款商品总表"

            # 写入表头
            ws.append(headers)

            # 表头样式设计 (深蓝背景，白色粗体)
            header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
            header_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
            align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
            align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)

            thin_border = Border(
                left=Side(style='thin', color='D9D9D9'),
                right=Side(style='thin', color='D9D9D9'),
                top=Side(style='thin', color='D9D9D9'),
                bottom=Side(style='thin', color='D9D9D9')
            )

            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = align_center

            # 写入数据行
            for r_idx, row_data in enumerate(rows, start=2):
                ws.append(row_data)
                # 为每行设置边框和对齐
                for c_idx in range(1, len(headers) + 1):
                    cell = ws.cell(row=r_idx, column=c_idx)
                    cell.border = thin_border
                    cell.font = Font(name="微软雅黑", size=10)
                    if c_idx in [1, 3, 4, 5, 9]:
                        cell.alignment = align_center
                    else:
                        cell.alignment = align_left

            # 自动调整列宽
            col_widths = {
                1: 14,  # 平台
                2: 45,  # 商品名称
                3: 12,  # 价格
                4: 14,  # 销量
                5: 14,  # 评分
                6: 22,  # 店铺
                7: 40,  # 链接
                8: 30,  # 素材文件夹
                9: 20   # 时间
            }
            for col_idx, width in col_widths.items():
                col_letter = openpyxl.utils.get_column_letter(col_idx)
                ws.column_dimensions[col_letter].width = width

            wb.save(filepath)
            print(f"[SUCCESS] Excel 选品报表已生成: {filepath}")
            return filepath

        except Exception as e:
            print(f"[WARN] Excel 导出遇到异常，降级导出 CSV: {e}")
            csv_path = os.path.splitext(filepath)[0] + ".csv"
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as cf:
                writer = csv.writer(cf)
                writer.writerow(headers)
                writer.writerows(rows)
            print(f"[SUCCESS] CSV 报表已生成: {csv_path}")
            return csv_path

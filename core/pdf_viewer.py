import os
import sys
import json
import tempfile
import base64
from pathlib import Path
import fitz  # PyMuPDF
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QApplication, 
                            QGraphicsView, QGraphicsScene, QScrollArea, QHBoxLayout, QFrame, QPushButton, QTextEdit, QGroupBox)
from PyQt6.QtCore import QUrl, QObject, pyqtSlot, pyqtSignal, QSize, QBuffer, QByteArray, QIODevice, Qt
from PyQt6.QtGui import QPixmap, QImage, QPainter
import re

class PDFHeaderViewer(QWidget):
    """
    Componente para renderizar PDFs usando PyMuPDF (fitz)
    Isso permite uma renderização precisa dos PDFs sem a necessidade de QtWebEngineWidgets
    """
    header_captured = pyqtSignal(str, object, dict)  # Sinal emitido quando o cabeçalho é capturado

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.current_pdf_path = None
        self.header_data = {}
        self.current_zoom = 1.0  # Nível de zoom inicial (100%)
        self.pixmaps = []        # Armazenar os pixmaps de todas as páginas
        self.current_page = 0    # Página atual
        self.total_pages = 0     # Total de páginas no documento
        
    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        
        # Adicionar controles de zoom e página
        controls_layout = QHBoxLayout()
        
        # Configurar estilos para os botões
        button_style = """
            QPushButton {
                background-color: #1a237e;  /* Azul escuro */
                color: #ffffff;             /* Texto branco */
                border: 1px solid #3949ab;
                border-radius: 4px;
                padding: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #283593;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #0d133d;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #e8eaf6;
                color: #b0b0b0;
            }
        """
        
        # Controles de zoom
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setFixedSize(40, 40)
        self.zoom_out_btn.setStyleSheet(button_style)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.zoom_out_btn.setToolTip("Diminuir zoom")
        
        self.zoom_reset_btn = QPushButton("100%")
        self.zoom_reset_btn.setFixedSize(80, 40)
        self.zoom_reset_btn.setStyleSheet(button_style)
        self.zoom_reset_btn.clicked.connect(self.zoom_reset)
        self.zoom_reset_btn.setToolTip("Restaurar zoom original")
        
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedSize(40, 40)
        self.zoom_in_btn.setStyleSheet(button_style)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_in_btn.setToolTip("Aumentar zoom")
        
        self.fit_to_view_btn = QPushButton("Ajustar")
        self.fit_to_view_btn.setFixedWidth(100)
        self.fit_to_view_btn.setFixedHeight(40)
        self.fit_to_view_btn.setStyleSheet(button_style)
        self.fit_to_view_btn.clicked.connect(self.fit_to_view)
        self.fit_to_view_btn.setToolTip("Ajustar à janela")
        
        # Adicionar separador
        controls_layout.addWidget(self.zoom_out_btn)
        controls_layout.addWidget(self.zoom_reset_btn)
        controls_layout.addWidget(self.zoom_in_btn)
        controls_layout.addWidget(self.fit_to_view_btn)
        controls_layout.addStretch()
        
        # Controles de navegação de página
        self.prev_page_btn = QPushButton("< Anterior")
        self.prev_page_btn.setFixedWidth(120)
        self.prev_page_btn.setFixedHeight(40)
        self.prev_page_btn.setStyleSheet(button_style)
        self.prev_page_btn.clicked.connect(self.prev_page)
        self.prev_page_btn.setEnabled(False)
        
        self.page_label = QLabel("Página 1 de 1")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setFixedWidth(150)
        self.page_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        
        self.next_page_btn = QPushButton("Próxima >")
        self.next_page_btn.setFixedWidth(120)
        self.next_page_btn.setFixedHeight(40)
        self.next_page_btn.setStyleSheet(button_style)
        self.next_page_btn.clicked.connect(self.next_page)
        self.next_page_btn.setEnabled(False)
        
        controls_layout.addWidget(self.prev_page_btn)
        controls_layout.addWidget(self.page_label)
        controls_layout.addWidget(self.next_page_btn)
        
        self.layout.addLayout(controls_layout)
        
        # Área de scroll para visualizar o PDF
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        
        # Label para exibir o PDF renderizado
        self.pdf_label = QLabel()
        self.pdf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.pdf_label)
        
        self.layout.addWidget(self.scroll_area)

        # Botão para editar cabeçalho
        self.edit_header_btn = QPushButton("Editar Cabeçalho")
        self.edit_header_btn.setFixedHeight(40)
        self.edit_header_btn.setStyleSheet("""
            QPushButton {
                background-color: #00897b;
                color: #ffffff;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #26a69a;
            }
        """)
        self.edit_header_btn.clicked.connect(self.toggle_header_section)
        self.layout.addWidget(self.edit_header_btn)

        # Seção de edição do cabeçalho (inicialmente oculta)
        self.header_group = QGroupBox("Cabeçalho do Documento")
        self.header_group.setVisible(False)
        header_layout = QVBoxLayout()
        self.header_edit = QTextEdit()
        self.header_edit.setPlaceholderText("Edite ou crie o cabeçalho aqui...")
        header_layout.addWidget(self.header_edit)

        # Botão para salvar alterações no cabeçalho
        self.save_header_btn = QPushButton("Salvar Cabeçalho")
        self.save_header_btn.setStyleSheet("""
            QPushButton {
                background-color: #3949ab;
                color: #fff;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5c6bc0;
            }
        """)
        self.save_header_btn.clicked.connect(self.save_header)
        header_layout.addWidget(self.save_header_btn)
        self.header_group.setLayout(header_layout)
        self.layout.addWidget(self.header_group)
    
    def zoom_in(self):
        """Aumenta o zoom"""
        self.current_zoom *= 1.2
        self.update_zoom()
        
    def zoom_out(self):
        """Diminui o zoom"""
        self.current_zoom *= 0.8
        self.update_zoom()
        
    def zoom_reset(self):
        """Reinicia o zoom para 100%"""
        self.current_zoom = 1.0
        self.update_zoom()
        
    def fit_to_view(self):
        """Ajusta o zoom para que o PDF caiba completamente na tela"""
        if self.current_page < len(self.pixmaps) and self.pixmaps[self.current_page]:
            # Calcula o fator de escala para ajustar à largura e altura do scroll_area
            view_width = self.scroll_area.width() - 20  # Margem para scrollbar
            view_height = self.scroll_area.height() - 20  # Margem para scrollbar
            
            pixmap = self.pixmaps[self.current_page]
            scale_w = view_width / pixmap.width()
            scale_h = view_height / pixmap.height()
            
            # Usa o menor valor para garantir que o documento inteiro caiba
            self.current_zoom = min(scale_w, scale_h)
            
            self.update_zoom()
    
    def prev_page(self):
        """Navega para a página anterior"""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_page()
            
    def next_page(self):
        """Navega para a próxima página"""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_page()
    
    def update_page(self):
        """Atualiza a exibição da página atual"""
        # Atualiza o texto do indicador de página
        self.page_label.setText(f"Página {self.current_page + 1} de {self.total_pages}")
        
        # Atualiza os botões de navegação
        self.prev_page_btn.setEnabled(self.current_page > 0)
        self.next_page_btn.setEnabled(self.current_page < self.total_pages - 1)
        
        # Exibe a página atual com o zoom correto
        self.update_zoom()
            
    def update_zoom(self):
        """Atualiza a visualização com o zoom atual"""
        if self.current_page < len(self.pixmaps) and self.pixmaps[self.current_page]:
            # Atualiza o texto do botão de reset de zoom
            zoom_percent = int(self.current_zoom * 100)
            self.zoom_reset_btn.setText(f"{zoom_percent}%")
            
            # Redimensiona o pixmap de acordo com o zoom
            pixmap = self.pixmaps[self.current_page]
            scaled_width = int(pixmap.width() * self.current_zoom)
            scaled_height = int(pixmap.height() * self.current_zoom)
            
            scaled_pixmap = pixmap.scaled(
                scaled_width,
                scaled_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            self.pdf_label.setPixmap(scaled_pixmap)
            
            # Garantir que o label seja grande o suficiente para o pixmap
            self.pdf_label.setMinimumSize(scaled_width, scaled_height)
        
    def load_pdf(self, pdf_path):
        """Carrega um PDF e renderiza usando PyMuPDF (fitz)"""
        self.current_pdf_path = pdf_path
        self.pixmaps = []  # Limpa pixmaps anteriores
        
        try:
            # Abre o documento PDF com PyMuPDF
            doc = fitz.open(pdf_path)
            self.total_pages = len(doc)
            
            if self.total_pages > 0:
                # Renderizar todas as páginas
                for page_num in range(self.total_pages):
                    # Pega a página
                    page = doc[page_num]
                    
                    # Ajustar o fator de zoom para renderização inicial
                    # Para documents A4, usamos um fator que gera uma visualização similar ao Word
                    # Tamanho A4 em pixels a 96 DPI: 794 x 1123
                    # O zoom de renderização é alto para qualidade, mas será escalado depois
                    zoom = 2.0  # Fator de zoom para renderização em alta qualidade
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat)

                    # Converte para QImage
                    img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)

                    # Cria um QPixmap a partir da QImage e armazena
                    pixmap = QPixmap.fromImage(img)
                    self.pixmaps.append(pixmap)
                
                # Configurar navegação de páginas
                self.current_page = 0
                
                # Definir zoom inicial para 100%
                self.current_zoom = 1.0
                
                # Ajustar a largura do widget para simular a exibição do Word
                if len(self.pixmaps) > 0:
                    # Obter o tamanho disponível na área de visualização
                    view_width = self.scroll_area.width() - 30  # Margem para scrollbar vertical
                    
                    # Calcula o fator de escala para melhor aproveitamento
                    # Tamanho típico em proporção similar ao Word
                    ideal_width = 650  # Largura ideal em pixels
                    
                    # Obter a largura atual do pixmap em 100%
                    pixmap_width = self.pixmaps[0].width()
                    
                    # Ajustar o zoom para dar uma proporção similar ao Word
                    # Mantém-se em 100% visualmente, mas a escala real é ajustada
                    if pixmap_width > ideal_width:
                        scale_factor = ideal_width / pixmap_width
                        
                        # Aplicamos o fator de escala aos pixmaps
                        for i, pixmap in enumerate(self.pixmaps):
                            new_width = int(pixmap.width() * scale_factor)
                            new_height = int(pixmap.height() * scale_factor)
                            scaled_pixmap = pixmap.scaled(
                                new_width, 
                                new_height,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation
                            )
                            self.pixmaps[i] = scaled_pixmap
                
                # Atualizar a visualização
                self.update_page()
                
                # Mostrar/ocultar controles de navegação conforme necessário
                self.prev_page_btn.setVisible(self.total_pages > 1)
                self.next_page_btn.setVisible(self.total_pages > 1)
                self.page_label.setVisible(self.total_pages > 1)
                
                # Se tiver apenas uma página, botões de navegação não são necessários
                if self.total_pages <= 1:
                    self.prev_page_btn.hide()
                    self.next_page_btn.hide()
                    self.page_label.hide()
                
                # Captura as informações do cabeçalho sem modificá-lo
                self._extract_header_data(doc, doc[0])
                # Atualiza o editor de cabeçalho se estiver visível
                if self.header_group.isVisible():
                    self.header_edit.setPlainText(self.get_header_text())

                # Fecha o documento
                doc.close()
                
        except Exception as e:
            print(f"Erro ao carregar PDF: {e}")
            
    def _extract_header_data(self, doc, page):
        """Extrai os dados do cabeçalho sem modificar a visualização"""
        try:
            # Definir altura do cabeçalho (25% da primeira página)
            header_height_percentage = 0.25
            header_height = int(page.rect.height * header_height_percentage)
            
            # Criar dados estruturados para o cabeçalho
            self.header_data = {
                "text_elements": [],
                "left_image": None,
                "right_image": None
            }
            
            # Extrair texto do cabeçalho
            header_text_dict = page.get_text("dict", clip=fitz.Rect(0, 0, page.rect.width, header_height))
            
            # Extrair informações de imagens
            image_list = []
            for img_info in page.get_image_info():
                if img_info['bbox'][1] < header_height:
                    image_list.append(img_info)
            
            # Processar imagens se necessário
            temp_dir = Path("output/temp")
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Dividir imagens entre esquerda e direita
            page_center_x = page.rect.width / 2
            left_images = []
            right_images = []
            
            for img_info in image_list:
                img_center_x = (img_info['bbox'][0] + img_info['bbox'][2]) / 2
                if img_center_x < page_center_x:
                    left_images.append(img_info)
                else:
                    right_images.append(img_info)
            
            if left_images:
                left_images.sort(key=lambda x: (x['bbox'][2]-x['bbox'][0])*(x['bbox'][3]-x['bbox'][1]), reverse=True)
                left_img_info = left_images[0]
                self.header_data["left_image"] = {
                    "bbox": left_img_info['bbox']
                }
            
            if right_images:
                right_images.sort(key=lambda x: (x['bbox'][2]-x['bbox'][0])*(x['bbox'][3]-x['bbox'][1]), reverse=True)
                right_img_info = right_images[0]
                self.header_data["right_image"] = {
                    "bbox": right_img_info['bbox']
                }
                
            # Extrair elementos de texto
            if "blocks" in header_text_dict:
                for block in header_text_dict["blocks"]:
                    if "lines" in block:
                        for line in block["lines"]:
                            for span in line.get("spans", []):
                                text_element = {
                                    "text": span.get("text", ""),
                                    "bbox": span.get("bbox", [0, 0, 0, 0]),
                                    "fontSize": span.get("size", 12),
                                    "fontName": span.get("font", ""),
                                }
                                self.header_data["text_elements"].append(text_element)
            
            # Emite o sinal com os dados do cabeçalho
            self.header_captured.emit(
                self.current_pdf_path,
                None,  # Não estamos criando uma imagem do cabeçalho
                self.header_data
            )
            
        except Exception as e:
            print(f"Erro ao extrair dados do cabeçalho: {e}")
    
    def _get_temp_file_path(self):
        """Cria um arquivo temporário para salvar a imagem do cabeçalho"""
        temp_dir = Path("output/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        return str(temp_dir / f"header_temp_{hash(self.current_pdf_path)}.png")

    def toggle_header_section(self):
        """Mostra ou oculta a seção de edição do cabeçalho"""
        visible = not self.header_group.isVisible()
        self.header_group.setVisible(visible)
        if visible:
            # Preenche o editor com o cabeçalho atual, se houver
            header_text = self.get_header_text()
            self.header_edit.setPlainText(header_text)

    def get_header_text(self):
        """Obtém o texto do cabeçalho atual, se existir"""
        if self.header_data and self.header_data.get("text_elements"):
            # Junta os textos dos elementos do cabeçalho
            return "\n".join([el["text"] for el in self.header_data["text_elements"] if el["text"].strip()])
        return ""

    def save_header(self):
        """Salva as alterações feitas no cabeçalho e atualiza a preview"""
        new_header = self.header_edit.toPlainText()
        # Atualiza os dados do cabeçalho
        self.header_data["text_elements"] = [{
            "text": line,
            "bbox": [0, 0, 0, 0],  # Pode ser ajustado conforme necessário
            "fontSize": 12,
            "fontName": "Arial"
        } for line in new_header.splitlines() if line.strip()]
        # Atualiza a preview (pode ser customizado para mostrar o novo cabeçalho)
        self.update_preview_with_header()

    def update_preview_with_header(self):
        """Atualiza a preview para refletir o novo cabeçalho"""
        # Aqui você pode implementar a lógica para atualizar a preview do PDF
        # com o novo cabeçalho. Por simplicidade, apenas atualiza o sinal.
        self.header_captured.emit(
            self.current_pdf_path,
            None,
            self.header_data
        )

import logging
import os
import json
import time
import io
import tempfile
from datetime import datetime
import qrcode
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Spacer, ListFlowable, ListItem
from config.settings import BASE_DIR

# Configurar logging
logger = logging.getLogger(__name__)
log_file = os.path.join(BASE_DIR, "output", "prova_generation.log")
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class PDFGenerator:
    def __init__(self, questions=None, options=None):
        """Inicializa o gerador PDF com questões e opções"""
        self.questions = questions or []
        self.options = options or {}
        
        # Registra fontes padrão
        self._register_fonts()
        
        # Estilos de texto
        self.styles = getSampleStyleSheet()
        self.text_style = self.styles['Normal']
        
    def _register_fonts(self):
        """Registra fontes necessárias"""
        pdfmetrics.registerFont(TTFont('Arial', os.path.join(BASE_DIR, 'assets', 'Arial.ttf')))
        
    def add_qr_code(self, canvas, page_width, page_height, data="https://exemplo.com"):
        """Adiciona um QR code à página"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            # Gerar e salvar o QR code temporariamente
            img = qr.make_image(fill_color="black", back_color="white")
            temp_path = os.path.join(BASE_DIR, "output", "provas_geradas", "qrcode_temp.png")
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            img.save(temp_path)
            
            # Definir tamanho e posição do QR code (no rodapé, direita)
            qr_width = 50  # em pontos (cerca de 1.8 cm)
            margin = 20
            qr_x = page_width - qr_width - margin
            qr_y = margin
            
            # Adicionar ao Canvas
            canvas.drawImage(temp_path, qr_x, qr_y, width=qr_width, height=qr_width)
            
            logger.info(f"QR code adicionado com sucesso: {data}")
        except Exception as e:
            logger.error(f"Erro ao adicionar QR code: {str(e)}")
    
    def add_original_header(self, canvas, original_format):
        """Adiciona o cabeçalho original com máxima fidelidade"""
        try:
            # Verificar se temos o cabeçalho original para preservar
            header_images = original_format.get('header_images', [])
            all_images = original_format.get('all_images', [])
            image_sizes = original_format.get('image_sizes', {})
            exact_text_positions = original_format.get('exact_text_positions', [])
            header_content = original_format.get('original_header_content', [])
            filename = original_format.get('filename', '')
            
            # 1. Adicionar imagens com suas posições e tamanhos exatos
            for img_path in all_images:
                if os.path.exists(img_path) and os.path.getsize(img_path) > 0:
                    if img_path in image_sizes:
                        size_info = image_sizes[img_path]
                        
                        # Converter mm para pontos para o ReportLab
                        # 1mm = 2.83465 pontos
                        x_pos_pt = size_info.get('x', 0) * 2.83465
                        # Corrigido: não inverter o eixo Y
                        y_pos_pt = size_info.get('y', 0) * 2.83465
                        width_pt = size_info.get('width', 0) * 2.83465
                        height_pt = size_info.get('height', 0) * 2.83465
                        
                        # Adicionar a imagem com posicionamento preciso
                        canvas.drawImage(img_path, x_pos_pt, y_pos_pt, width=width_pt, height=height_pt, mask='auto')
            
            # 2. Adicionar texto com posicionamento e formatação exatos
            if exact_text_positions:
                for text_pos in exact_text_positions:
                    text = text_pos.get('text', '')
                    if not text:
                        continue
                        
                    # Obter coordenadas
                    x0 = text_pos.get('x0', 0)
                    y0 = text_pos.get('y0', 0)
                    # Inverter coordenada Y (ReportLab começa de baixo)
                    y0 = A4[1] - y0
                    
                    # Configurar fonte
                    font_name = text_pos.get('font', 'Arial')
                    # Verificar se precisamos registrar essa fonte
                    if font_name not in pdfmetrics._fonts:
                        try:
                            # Tentar registrar a fonte se não for padrão
                            if font_name.lower() not in ['arial', 'helvetica', 'times-roman', 'courier']:
                                font_path = os.path.join(BASE_DIR, 'assets', f'{font_name}.ttf')
                                if os.path.exists(font_path):
                                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                        except:
                            # Fallback para Arial se não conseguir registrar a fonte
                            font_name = 'Arial'
                    
                    # Configurar fonte no canvas
                    font_size = text_pos.get('size', 12)
                    canvas.setFont(font_name, font_size)
                    
                    # Configurar estilo (negrito, itálico)
                    flags = text_pos.get('flags', 0)
                    # ReportLab não suporta flags diretamente, então usamos a fonte apropriada
                    
                    # Configurar cor
                    color_value = text_pos.get('color', 0)
                    if isinstance(color_value, int):
                        r = (color_value >> 16) & 0xFF
                        g = (color_value >> 8) & 0xFF
                        b = color_value & 0xFF
                        canvas.setFillColorRGB(r/255, g/255, b/255)
                    
                    # Desenhar o texto na posição exata
                    canvas.drawString(x0, y0, text)
            
            # 3. Para documentos PDF, adicionar estrutura de blocos
            elif isinstance(header_content, list) and header_content and isinstance(header_content[0], dict) and 'lines' in header_content[0]:
                # Processar blocos de cabeçalho de PDF
                for block in header_content:
                    if 'lines' in block:
                        for line in block['lines']:
                            if 'spans' in line:
                                for span in line['spans']:
                                    # Obter propriedades do texto
                                    text = span.get('text', '').strip()
                                    if not text:
                                        continue
                                    
                                    # Coordenadas
                                    x0 = span.get('origin', [0, 0])[0]
                                    y0 = span.get('origin', [0, 0])[1]
                                    # Inverter coordenada Y
                                    y0 = A4[1] - y0
                                    
                                    # Fonte
                                    font_name = span.get('font', 'Arial')
                                    if font_name not in pdfmetrics._fonts:
                                        try:
                                            if font_name.lower() not in ['arial', 'helvetica', 'times-roman', 'courier']:
                                                font_path = os.path.join(BASE_DIR, 'assets', f'{font_name}.ttf')
                                                if os.path.exists(font_path):
                                                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                                        except:
                                            font_name = 'Arial'
                                    
                                    # Tamanho e cor
                                    font_size = span.get('size', 12)
                                    canvas.setFont(font_name, font_size)
                                    
                                    color_value = span.get('color', 0)
                                    if isinstance(color_value, int):
                                        r = (color_value >> 16) & 0xFF
                                        g = (color_value >> 8) & 0xFF
                                        b = color_value & 0xFF
                                        canvas.setFillColorRGB(r/255, g/255, b/255)
                                    
                                    # Desenhar texto
                                    canvas.drawString(x0, y0, text)
                                    
                                    # Adicionar sublinhado se necessário
                                    flags = span.get('flags', 0)
                                    if flags & 4:  # Underline flag
                                        text_width = canvas.stringWidth(text)
                                        canvas.line(x0, y0 - 2, x0 + text_width, y0 - 2)
            
            # 4. Para documentos DOCX, adicionar parágrafos formatados
            elif isinstance(header_content, list) and header_content and 'text' in header_content[0]:
                # Processar parágrafos de cabeçalho DOCX
                y_offset = A4[1] - 30  # Posição inicial (topo - margem)
                for paragraph in header_content:
                    text = paragraph.get('text', '').strip()
                    if not text:
                        continue
                    
                    # Se tivermos runs (formatação detalhada)
                    if paragraph.get('runs'):
                        # Dividir o parágrafo em runs com formatação individual
                        current_x = A4[0] / 2  # Centralizar horizontalmente
                        
                        # Calcular largura total do parágrafo
                        total_width = 0
                        for run in paragraph.get('runs', []):
                            run_text = run.get('text', '')
                            if not run_text:
                                continue
                            
                            font_name = run.get('font', 'Arial')
                            font_size = run.get('size', 12)
                            if hasattr(font_size, 'pt'):
                                font_size = font_size.pt
                            
                            # Registrar fonte se necessário
                            if font_name not in pdfmetrics._fonts:
                                try:
                                    if font_name.lower() not in ['arial', 'helvetica', 'times-roman', 'courier']:
                                        font_path = os.path.join(BASE_DIR, 'assets', f'{font_name}.ttf')
                                        if os.path.exists(font_path):
                                            pdfmetrics.registerFont(TTFont(font_name, font_path))
                                except:
                                    font_name = 'Arial'
                            
                            canvas.setFont(font_name, font_size)
                            total_width += canvas.stringWidth(run_text)
                        
                        # Ajustar posição inicial para centralização
                        current_x = (A4[0] - total_width) / 2
                        
                        # Desenhar cada run com sua formatação
                        for run in paragraph.get('runs', []):
                            run_text = run.get('text', '')
                            if not run_text:
                                continue
                            
                            # Aplicar formatação
                            font_name = run.get('font', 'Arial')
                            font_size = run.get('size', 12)
                            if hasattr(font_size, 'pt'):
                                font_size = font_size.pt
                            
                            canvas.setFont(font_name, font_size)
                            
                            # Aplicar cor
                            color_rgb = run.get('color')
                            if color_rgb:
                                r = (color_rgb >> 16) & 0xFF
                                g = (color_rgb >> 8) & 0xFF
                                b = color_rgb & 0xFF
                                canvas.setFillColorRGB(r/255, g/255, b/255)
                            else:
                                canvas.setFillColorRGB(0, 0, 0)  # Preto padrão
                            
                            # Desenhar o texto
                            canvas.drawString(current_x, y_offset, run_text)
                            
                            # Adicionar sublinhado se necessário
                            if run.get('style', {}).get('underline'):
                                text_width = canvas.stringWidth(run_text)
                                canvas.line(current_x, y_offset - 2, current_x + text_width, y_offset - 2)
                            
                            # Avançar a posição X para o próximo run
                            current_x += canvas.stringWidth(run_text)
                    else:
                        # Parágrafo simples centralizado
                        canvas.setFont('Arial', 12)
                        canvas.setFillColorRGB(0, 0, 0)  # Preto
                        text_width = canvas.stringWidth(text)
                        canvas.drawString((A4[0] - text_width) / 2, y_offset, text)
                    
                    # Próximo parágrafo mais abaixo
                    y_offset -= 15
            
            # Resetar para cor preta padrão após desenhar o cabeçalho
            canvas.setFillColorRGB(0, 0, 0)
            logger.info("Cabeçalho original adicionado com sucesso")
        
        except Exception as e:
            logger.error(f"Erro ao adicionar cabeçalho original: {str(e)}")
            # Continuar mesmo com erro, para não impedir a geração do PDF
    
    def generate_pdf(self, output_path, metadata=None):
        """Gera um PDF formatado com questões e opções"""
        logger.info(f"Iniciando geração de PDF: {output_path}")
        
        # Criar diretório de saída se não existir
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Tamanho da página
        page_width, page_height = A4
        
        # Margens
        margin = 50
        
        # Criar um buffer para o PDF
        buffer = io.BytesIO()
        
        # Criar canvas
        c = canvas.Canvas(buffer, pagesize=A4)
        c.setTitle(metadata.get('title', 'Prova') if metadata else 'Prova')
        
        # Adicionar cabeçalho original se disponível
        original_format = metadata.get('formato_original', {}) if metadata else {}
        preservar_cabecalho = original_format.get('preserve_original_header', False)
        
        if preservar_cabecalho:
            self.add_original_header(c, original_format)
            # Após adicionar o cabeçalho, movemos a posição Y para abaixo dele
            current_y = page_height - 150  # ~5cm do topo
        else:
            # Cabeçalho padrão simples
            c.setFont("Arial", 12)
            c.drawString(margin, page_height - margin, "AVALIAÇÃO DE CONHECIMENTOS")
            c.drawString(margin, page_height - margin - 20, "Data: " + time.strftime("%d/%m/%Y"))
            current_y = page_height - margin - 50
        
        # Linha horizontal após o cabeçalho
        c.line(margin, current_y, page_width - margin, current_y)
        current_y -= 20
        
        # Adicionar instruções
        c.setFont("Arial", 11)
        c.drawString(margin, current_y, "INSTRUÇÕES:")
        current_y -= 15
        c.setFont("Arial", 10)
        
        instrucoes = [
            "1. Leia todas as questões atentamente.",
            "2. Cada questão tem apenas uma resposta correta.",
            "3. Não é permitido consultar materiais externos durante a prova."
        ]
        
        for instrucao in instrucoes:
            c.drawString(margin + 10, current_y, instrucao)
            current_y -= 15
        
        # Linha horizontal após as instruções
        current_y -= 10
        c.line(margin, current_y, page_width - margin, current_y)
        current_y -= 20
        
        # Adicionar questões
        texto_questao_estilo = ParagraphStyle(
            'QuestaoEstilo',
            parent=self.styles['Normal'],
            fontName='Arial',
            fontSize=10,
            leading=12,
            spaceAfter=6
        )
        
        texto_alternativa_estilo = ParagraphStyle(
            'AlternativaEstilo',
            parent=self.styles['Normal'],
            fontName='Arial',
            fontSize=10,
            leading=12,
            leftIndent=20
        )
        
        # Verificar como estão formatadas as questões
        for idx, (enunciado, alternativas) in enumerate(self.questions, 1):
            # Verificar se este bloco é uma tabela no formato original
            is_table = False
            table_data = None
            
            if 'blocks' in original_format:
                for bloco in original_format.get('blocks', []):
                    if bloco.get('is_table', False) and enunciado in bloco.get('text', ''):
                        is_table = True
                        table_data = bloco
                        break
            
            # Se for uma tabela, renderizar como tabela
            if is_table and table_data:
                # Encontrar tabela correspondente na lista de tabelas com estrutura detalhada
                tabela_detalhada = None
                for tabela in original_format.get('tables', []):
                    if tabela.get('text', '') == table_data.get('text', ''):
                        tabela_detalhada = tabela
                        break
                
                # Desenhar a tabela
                if tabela_detalhada and tabela_detalhada.get('estrutura_detectada', False):
                    linhas = tabela_detalhada.get('linhas', enunciado.split('\n'))
                    
                    # Determinar a estrutura da tabela
                    tem_cabecalho = False
                    if len(linhas) > 1:
                        segunda_linha = linhas[1] if len(linhas) > 1 else ""
                        if segunda_linha and all(c in '-+=' for c in segunda_linha if c.strip()):
                            tem_cabecalho = True
                    
                    # Posição inicial e configurações
                    table_x = margin
                    table_y = current_y
                    
                    # Determinar as colunas
                    colunas_detectadas = []
                    for linha in linhas:
                        if '|' in linha:
                            # Separar por pipes
                            cols = [col.strip() for col in linha.split('|')]
                            # Remover células vazias nas extremidades
                            if cols and not cols[0].strip():
                                cols.pop(0)
                            if cols and not cols[-1].strip():
                                cols.pop()
                            
                            if len(cols) > len(colunas_detectadas):
                                colunas_detectadas = cols
                        elif '\t' in linha:
                            # Separar por tabs
                            cols = [col.strip() for col in linha.split('\t')]
                            if len(cols) > len(colunas_detectadas):
                                colunas_detectadas = cols
                    
                    # Se não encontramos colunas, tentar outra abordagem
                    if not colunas_detectadas:
                        import re
                        for linha in linhas:
                            if linha and not all(c in '-+=' for c in linha if c.strip()):
                                # Tentar separar por múltiplos espaços
                                cols = [col.strip() for col in re.split(r'\s{2,}', linha)]
                                if len(cols) > len(colunas_detectadas):
                                    colunas_detectadas = cols
                    
                    # Número de colunas e largura
                    num_colunas = max(1, len(colunas_detectadas))
                    col_width = (page_width - 2 * margin) / num_colunas
                    
                    # Altura da linha
                    linha_height = 20
                    
                    # Filtrar linhas separadoras
                    linhas_dados = [linha for linha in linhas if not all(c in '-+=' for c in linha.strip() if c.strip())]
                    
                    # Desenhar a tabela
                    for i, linha in enumerate(linhas_dados):
                        # Pular linhas vazias
                        if not linha.strip():
                            continue
                        
                        # Determinar se é linha de cabeçalho
                        e_cabecalho = (tem_cabecalho and i == 0)
                        
                        # Detectar colunas
                        colunas = []
                        if '|' in linha:
                            colunas = [col.strip() for col in linha.split('|')]
                            # Remover células vazias nas extremidades
                            if colunas and not colunas[0].strip():
                                colunas.pop(0)
                            if colunas and not colunas[-1].strip():
                                colunas.pop()
                        elif '\t' in linha:
                            colunas = [col.strip() for col in linha.split('\t')]
                        else:
                            # Tentar separar por múltiplos espaços
                            import re
                            colunas = [col.strip() for col in re.split(r'\s{2,}', linha)]
                        
                        # Se não detectamos colunas, tratar como célula única
                        if not colunas:
                            colunas = [linha]
                        
                        # Configurar fonte
                        if e_cabecalho:
                            # Cabeçalho em negrito
                            c.setFont("Arial-Bold", 10)
                        else:
                            c.setFont("Arial", 10)
                        
                        # Desenhar células
                        for j, coluna in enumerate(colunas):
                            if j < num_colunas:  # Limitar ao número máximo de colunas
                                x = table_x + (j * col_width)
                                
                                # Desenhar borda da célula
                                c.rect(x, table_y - linha_height, col_width, linha_height)
                                
                                # Desenhar texto da célula (centralizado vertical e horizontalmente)
                                text_width = c.stringWidth(coluna)
                                x_text = x + (col_width - text_width) / 2
                                y_text = table_y - linha_height / 2 - 5
                                c.drawString(x_text, y_text, coluna)
                        
                        # Próxima linha
                        table_y -= linha_height
                    
                    # Atualizar a posição Y atual
                    current_y = table_y - 20  # Espaço após a tabela
                else:
                    # Fallback - desenhar como texto normal se não tiver estrutura detalhada
                    lines = enunciado.split('\n')
                    c.setFont("Arial", 10)
                    for line in lines:
                        c.drawString(margin, current_y, line)
                        current_y -= 15
            else:
                # Não é tabela, renderizar como texto normal
                lines = enunciado.split('\n')
                c.setFont("Arial", 10)
                
                # Se o bloco original tiver informações de fonte, usá-las
                if original_format.get('blocks'):
                    for bloco in original_format.get('blocks', []):
                        if enunciado in bloco.get('text', ''):
                            if bloco.get('font_info') and len(bloco['font_info']) > 0:
                                font_info = bloco['font_info'][0]
                                font_name = font_info.get('font', 'Arial')
                                if font_info['style'].get('bold'):
                                    font_name += '-Bold'
                                font_size = font_info.get('size', 10)
                                c.setFont(font_name if font_name in pdfmetrics._fonts else 'Arial', font_size)
                                break
                
                # Renderizar linhas do enunciado preservando quebras
                for line in lines:
                    # Verificar se precisamos quebrar esta linha em múltiplas linhas
                    text_width = c.stringWidth(line)
                    available_width = page_width - 2 * margin
                    
                    if text_width <= available_width:
                        # Cabe em uma linha
                        c.drawString(margin, current_y, line)
                        current_y -= 15
                    else:
                        # Quebrar em múltiplas linhas
                        words = line.split()
                        current_line = ""
                        
                        for word in words:
                            test_line = current_line + " " + word if current_line else word
                            if c.stringWidth(test_line) <= available_width:
                                current_line = test_line
                            else:
                                c.drawString(margin, current_y, current_line)
                                current_y -= 15
                                current_line = word
                        
                        if current_line:  # Última linha do parágrafo
                            c.drawString(margin, current_y, current_line)
                            current_y -= 15
            
            # Espaço entre enunciado e alternativas
            current_y -= 5
            
            # Alternativas
            c.setFont("Arial", 10)
            for alternativa in alternativas:
                # Preservar quebras de linha das alternativas
                alt_lines = alternativa.split('\n')
                for i, alt_line in enumerate(alt_lines):
                    indent = margin + 20 if i == 0 else margin + 30  # Indentação para a primeira linha e subsequentes
                    
                    # Verificar se esta linha cabe na largura disponível
                    text_width = c.stringWidth(alt_line)
                    available_width = page_width - indent - margin
                    
                    if text_width <= available_width:
                        # Cabe em uma linha
                        c.drawString(indent, current_y, alt_line)
                        current_y -= 15
                    else:
                        # Quebrar em múltiplas linhas
                        words = alt_line.split()
                        current_line = ""
                        
                        for word in words:
                            test_line = current_line + " " + word if current_line else word
                            if c.stringWidth(test_line) <= available_width:
                                current_line = test_line
                            else:
                                c.drawString(indent, current_y, current_line)
                                current_y -= 15
                                current_line = word
                                indent = margin + 30  # Indentação para continuação
                        
                        if current_line:
                            c.drawString(indent, current_y, current_line)
                            current_y -= 15
            
            # Verificar se precisamos de uma nova página
            if current_y < 100:  # Aproximadamente 3cm do rodapé
                # Adicionar QR code na página atual
                self.add_qr_code(c, page_width, page_height, data="https://exemplo.com")
                
                # Nova página
                c.showPage()
                c.setFont("Arial", 10)
                current_y = page_height - margin
            else:
                # Espaço entre questões na mesma página
                current_y -= 20
        
        # Adicionar QR code na última página
        self.add_qr_code(c, page_width, page_height, data="https://exemplo.com")
        
        # Finalizar o documento e salvar
        c.showPage()
        c.save()
        
        # Salvar o buffer no arquivo
        with open(output_path, 'wb') as f:
            f.write(buffer.getvalue())
        
        logger.info(f"PDF gerado com sucesso: {output_path}")
        return output_path

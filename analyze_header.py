import fitz
import os
import json

def analyze_pdf_header(pdf_path):
    doc = fitz.open(pdf_path)
    page = doc[0]
    
    # Extrair informações do cabeçalho (primeiros 25% da página)
    header_height = page.rect.height * 0.25
    header_rect = fitz.Rect(0, 0, page.rect.width, header_height)
    
    # Extrair texto e suas propriedades
    header_dict = page.get_text("dict", clip=header_rect)
    
    # Extrair imagens
    images = []
    for img_index, img in enumerate(page.get_images(full=True)):
        xref = img[0]
        if xref:
            pix = fitz.Pixmap(doc, xref)
            if pix.width > 0 and pix.height > 0:
                # Obter informações posicionais da imagem
                for item in page.get_image_info():
                    if item.get('xref') == xref:
                        # Verificar se a imagem está no cabeçalho
                        if item['bbox'][1] <= header_height:
                            images.append({
                                'xref': xref,
                                'bbox': item['bbox'],
                                'width': pix.width,
                                'height': pix.height,
                                'position_mm': {
                                    'x': item['bbox'][0] * 0.352778,  # Converter para mm
                                    'y': item['bbox'][1] * 0.352778,
                                    'width': (item['bbox'][2] - item['bbox'][0]) * 0.352778,
                                    'height': (item['bbox'][3] - item['bbox'][1]) * 0.352778
                                }
                            })
    
    # Formatar informações do cabeçalho para análise
    header_info = {
        'page_size': {
            'width': page.rect.width,
            'height': page.rect.height,
            'width_mm': page.rect.width * 0.352778,
            'height_mm': page.rect.height * 0.352778
        },
        'header_height': header_height,
        'blocks': [],
        'images': images
    }
    
    # Extrair informações detalhadas de cada bloco de texto
    for block in header_dict.get('blocks', []):
        if block.get('type', -1) == 0:  # Bloco de texto
            block_info = {
                'bbox': block.get('bbox', []),
                'lines': []
            }
            
            for line in block.get('lines', []):
                line_info = {
                    'bbox': line.get('bbox', []),
                    'spans': []
                }
                
                for span in line.get('spans', []):
                    span_info = {
                        'text': span.get('text', ''),
                        'font': span.get('font', ''),
                        'size': span.get('size', 0),
                        'flags': span.get('flags', 0),  # 1=bold, 2=italic, 4=underline
                        'color': span.get('color', 0),
                        'origin': span.get('origin', []),
                        'bbox': span.get('bbox', [])
                    }
                    line_info['spans'].append(span_info)
                
                block_info['lines'].append(line_info)
            
            header_info['blocks'].append(block_info)
    
    doc.close()
    return header_info

def main():
    pdf_path = 'prova aja 8-9 1bim.pdf'
    if not os.path.exists(pdf_path):
        print(f"Erro: Arquivo {pdf_path} não encontrado!")
        return
    
    header_info = analyze_pdf_header(pdf_path)
    
    # Exibir informações do cabeçalho
    print("=== CABEÇALHO DO PDF ORIGINAL ===")
    
    # Informações da página
    print(f"\nTamanho da página: {header_info['page_size']['width_mm']:.2f}mm x {header_info['page_size']['height_mm']:.2f}mm")
    print(f"Altura do cabeçalho: {header_info['header_height'] * 0.352778:.2f}mm")
    
    # Informações das imagens
    if header_info['images']:
        print("\n--- IMAGENS NO CABEÇALHO ---")
        for i, img in enumerate(header_info['images']):
            print(f"\nImagem {i+1}:")
            print(f"Posição: x={img['position_mm']['x']:.2f}mm, y={img['position_mm']['y']:.2f}mm")
            print(f"Tamanho: {img['position_mm']['width']:.2f}mm x {img['position_mm']['height']:.2f}mm")
    
    # Informações dos blocos de texto
    print("\n--- BLOCOS DE TEXTO NO CABEÇALHO ---")
    for i, block in enumerate(header_info['blocks']):
        print(f"\nBloco {i+1}:")
        for j, line in enumerate(block['lines']):
            print(f"  Linha {j+1}:")
            for k, span in enumerate(line['spans']):
                flags_desc = []
                if span['flags'] & 1: flags_desc.append("negrito")
                if span['flags'] & 2: flags_desc.append("itálico")
                if span['flags'] & 4: flags_desc.append("sublinhado")
                flags_str = ", ".join(flags_desc) if flags_desc else "normal"
                
                # Converter cor para RGB
                color = span['color']
                r = (color >> 16) & 0xFF
                g = (color >> 8) & 0xFF
                b = color & 0xFF
                
                # Calcular posição em mm
                x_mm = span['origin'][0] * 0.352778
                y_mm = span['origin'][1] * 0.352778
                
                print(f"    Texto: \"{span['text']}\"")
                print(f"    Fonte: {span['font']}, {span['size']:.1f}pt, {flags_str}")
                print(f"    Cor: RGB({r},{g},{b})")
                print(f"    Posição: x={x_mm:.2f}mm, y={y_mm:.2f}mm")
    
    # Salvar informações em um arquivo JSON para uso posterior
    with open('header_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(header_info, f, ensure_ascii=False, indent=2)
    print("\nAnálise do cabeçalho salva em 'header_analysis.json'")

if __name__ == "__main__":
    main()
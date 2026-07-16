"""
debug_pdf_indexes.py
--------------------
Mostra come fitz estrae il testo dalle pagine del PDF, riga per riga,
evidenziando le righe che contengono pattern numerici tipo indici.

Uso:
    python debug_pdf_indexes.py "C:/percorso/FA020022045.pdf" 13 19
"""
import sys
import re


def show_pages(pdf_path: str, page_start: int, page_end: int):
    try:
        import fitz
    except ImportError:
        print("Esegui: pip install pymupdf")
        return
    with open("funzioni_debug_pdf_infexes.log", "w", encoding="utf-8") as f:
        
        pdf = fitz.open(pdf_path)
        f.write(f"PDF     : {pdf_path}")
        print(f"PDF     : {pdf_path}")
        f.write(f"Pagine  : {pdf.page_count} totali")
        print(f"Pagine  : {pdf.page_count} totali")        
        print("=" * 70)

        for page_num in range(page_start, page_end + 1):
            idx = page_num - 1
            if idx >= pdf.page_count:
                f.write(f"[Pagina {page_num}: oltre il limite]")
                print(f"[Pagina {page_num}: oltre il limite]")
                break

            text = pdf[idx].get_text()
            f.write(f"\n{'=' * 70}")
            print(f"\n{'=' * 70}")
            f.write(f"PAGINA {page_num}  ({len(text)} caratteri)")
            print(f"PAGINA {page_num}  ({len(text)} caratteri)")
            f.write(f"{'=' * 70}")
            print(f"{'=' * 70}")

            for i, line in enumerate(text.splitlines()):
                # repr mostra \xa0, \t, spazi multipli ecc. visibili
                repr_line = repr(line)[1:-1]
                looks_like_index = bool(re.search(r"\d+\.\d+", line))
                marker = ">>>" if looks_like_index else "   "
                f.write(f"{marker} [{i:3d}] {repr_line}\n")
                print(f"{marker} [{i:3d}] {repr_line}")

        pdf.close()
        f.write("\n" + "=" * 70)
        print("\n" + "=" * 70)
        f.write("Legenda: >>> = riga con pattern numerico (possibile indice)")
        print("Legenda: >>> = riga con pattern numerico (possibile indice)")
        f.write("         \\xa0 = spazio non-breaking  |  \\t = tabulazione")
        print("         \\xa0 = spazio non-breaking  |  \\t = tabulazione")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python debug_pdf_indexes.py <pdf> <pag_inizio> <pag_fine>")
        print("Es : python debug_pdf_indexes.py FA020022045.pdf 13 19")
        sys.exit(1)

    show_pages(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
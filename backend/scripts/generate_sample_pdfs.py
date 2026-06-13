"""Generate small synthetic biology PDFs for demo mode and tests.

The original spec referenced an OpenStax download URL that returns an HTML page
rather than a PDF, so this script instead produces three self-contained sample
PDFs with real biology text using PyMuPDF. Drop your own full-size OpenStax
PDFs into ``backend/pdfs/`` for a production-scale corpus.
"""
from __future__ import annotations

import os

import fitz

SAMPLES = {
    "biology2e_sample.pdf": [
        "Chapter 1: The Study of Life",
        (
            "Biology is the science that studies life and living organisms. "
            "All living things are composed of one or more cells, the basic "
            "unit of life. Cells arise from pre-existing cells through division."
        ),
        (
            "The mitochondrion is the powerhouse of the cell. It generates most "
            "of the cell's supply of adenosine triphosphate (ATP) through "
            "oxidative phosphorylation, which the cell uses as chemical energy."
        ),
        (
            "Photosynthesis is the process by which plants, algae, and some "
            "bacteria convert light energy into chemical energy stored in "
            "glucose. It occurs in the chloroplasts and releases oxygen."
        ),
    ],
    "cell_biology_notes.pdf": [
        "Cell Biology Notes",
        (
            "The cell membrane is a selectively permeable phospholipid bilayer "
            "that controls the movement of substances into and out of the cell. "
            "Embedded proteins enable transport, signaling, and adhesion."
        ),
        (
            "Ribosomes are the sites of protein synthesis. They translate "
            "messenger RNA into polypeptide chains using transfer RNA. "
            "Ribosomes may be free in the cytoplasm or bound to the ER."
        ),
        (
            "DNA carries the genetic instructions of the cell. During mitosis, "
            "the genetic material is replicated and equally distributed to two "
            "daughter cells, preserving the chromosome number."
        ),
    ],
    "genetics_guide.pdf": [
        "Genetics Quick Guide",
        (
            "A gene is a unit of heredity made of DNA. Alleles are alternative "
            "forms of a gene. The combination of alleles an organism carries is "
            "its genotype, while the observable traits form its phenotype."
        ),
        (
            "Mendel's law of segregation states that the two alleles for a trait "
            "separate during gamete formation, so each gamete carries only one "
            "allele for each gene."
        ),
        (
            "Mutations are changes in the DNA sequence. They can be neutral, "
            "harmful, or beneficial, and they are the ultimate source of the "
            "genetic variation on which natural selection acts."
        ),
    ],
}


def build(out_dir: str) -> None:
    """Write all sample PDFs into ``out_dir`` (one page per paragraph)."""
    os.makedirs(out_dir, exist_ok=True)
    for filename, paragraphs in SAMPLES.items():
        doc = fitz.open()
        for para in paragraphs:
            page = doc.new_page()
            rect = fitz.Rect(72, 72, 523, 770)
            page.insert_textbox(rect, para, fontsize=14, fontname="helv")
        path = os.path.join(out_dir, filename)
        doc.save(path)
        doc.close()
        print(f"wrote {path} ({len(paragraphs)} pages)")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(here, "..", "sample_pdfs")
    build(os.path.normpath(target))

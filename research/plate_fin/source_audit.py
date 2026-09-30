#!/usr/bin/env python3
"""Explicit optional source-byte/Figure8 audit; PDF is never needed for replay."""
import argparse,hashlib,json,pathlib,math
HERE=pathlib.Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--source-pdf',type=pathlib.Path,required=True);p.add_argument('--extract-figure8',action='store_true');p.add_argument('--output',type=pathlib.Path);a=p.parse_args()
 provenance=json.loads((HERE/'inputs/source_provenance.json').read_text()); expected=json.loads((HERE/'inputs/figure8_markers.json').read_text())
 checks={'source_byte_count':a.source_pdf.stat().st_size==provenance['source_pdf_expected_bytes'],'source_sha256':sha(a.source_pdf)==provenance['source_pdf_sha256']}
 assert all(checks.values()),'Only the provenance-bound PDF bytes are accepted'
 error=0.
 if a.extract_figure8:
  import fitz # Optional PyMuPDF, only for the explicit source extraction audit.
  with fitz.open(a.source_pdf) as pdf:
   ds=pdf[8].get_drawings();x4=ds[99]['rect'].x0;x22=ds[117]['rect'].x0;y2=ds[120]['rect'].y0;y9=ds[134]['rect'].y0;sx=18/(x22-x4);sy=.7/(y2-y9)
   for marker in expected['rows']:
    d=ds[marker['drawing_index']];r=d['rect'];x=(r.x0+r.x1)/2;y=(r.y0+r.y1)/2
    assert d['fill']==(0.,0.,0.) and len(d['items'])==1 and d['items'][0][0]=='re'
    actual=[x,y,4+(x-x4)*sx,.2+(y2-y)*sy,r.width/2*sx,r.height/2*sy]
    ref=marker['center_pdf_points']+[marker['V_channel_inferred_m_s'],marker['Rth_K_W'],marker['conservative_graphical_half_symbol_envelope']['V_m_s'],marker['conservative_graphical_half_symbol_envelope']['Rth_K_W']]
    for val,want in zip(actual,ref):
     error=max(error,abs(val-want));assert math.isclose(val,want,rel_tol=1e-12,abs_tol=1e-12)
  checks['all12_figure8_markers_match']=True
 out={'status':'passed','explicit_optional_source_audit':True,'source_pdf_sha256':provenance['source_pdf_sha256'],'source_pdf_redistributed':False,'checks':checks,'figure8_extracted':a.extract_figure8,'maximum_absolute_transcription_difference':error,'source_audit_script_sha256':sha(__file__),'original_extractor_sha256':provenance['original_extractor_sha256'],'marker_transcription_sha256':sha(HERE/'inputs/figure8_markers.json'),'claim':'Source-byte identity and marker transcription only; not physical validation.'}
 txt=json.dumps(out,indent=2)+'\n';a.output.write_text(txt) if a.output else print(txt)
if __name__=='__main__':main()

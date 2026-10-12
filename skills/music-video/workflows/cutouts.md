# Cutouts and parallax checklist
- [ ] `pip install --user "rembg[cpu]"` (model isnet-general-use downloads on first run, ~180 MB)
- [ ] Sheets: `python3 scripts/cutout_sheet.py source/<who>-sheet.jpg --count 4 --names ... -o cutouts/<who>`
- [ ] Group: `--count 5 --names <order> -o cutouts/dance` (touching figures get equal-width splits; check for clipped capes/limbs)
- [ ] Review on a checker/magenta background: no gray halo, no missing hands/props, no neighbor fragments
- [ ] Backgrounds (2048x1152): far = full plate with 1-1.5 px blur; near = rows below ~70-80% height with a 7% feathered top edge, as PNG
  ```python
  y0=int(H*0.72); a=np.clip((y-y0)/(H*.07),0,1)*255  # alpha for the near band
  ```
- [ ] Layers in stage: far in `data-depth="0.3"`, near + actors in `data-depth="1"`; slow pan on the far plate
- [ ] Labeled contact sheet → user approval; manifest statuses updated

// node shots/kingdom-come-16bit/tools/stills.mjs <outdir> label=seconds ...   (4x stills; wrapper over scripts/pixel_stills.mjs)
process.argv.splice(2, 0, 'kingdom-come-16bit');
await import('../../../scripts/pixel_stills.mjs');

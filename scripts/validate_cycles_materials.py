#!/usr/bin/env hython
"""Validate native Cycles texture networks with Houdini and cycles-material_nodes.hda installed.

Run: hython scripts/validate_cycles_materials.py
"""
import sys,json,tempfile
from pathlib import Path
import hou
from pxr import UsdShade
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root/'python'))
from automated_texture_builder.houdini.materials import build_materials
maps={k:{'path':'','color_space':'Raw','tiles':[]} for k in ['base_color','base_metalness','specular_roughness','normal','coat_normal','height','emission_color','opacity']}
with tempfile.TemporaryDirectory() as t:
 image=Path(t)/'texture.ppm'
 image.write_bytes(b'P6\n2 2\n255\n'+bytes([128,128,255])*4)
 for info in maps.values(): info['path']=str(image)
 p=Path(t)/'manifest.json'
 for mode,detail in [('auto','auto'),('repeat','bump'),('triplanar','auto'),('repeat','displacement')]:
  selected={key:dict(value) for key,value in maps.items()}
  if mode=='auto':
   for tile in (1001,1002):
    (Path(t)/f'texture.{tile}.ppm').write_bytes(image.read_bytes())
   for info in selected.values():
    info['path']=str(Path(t)/'texture.<UDIM>.ppm');info['tiles']=[1001,1002]
  if detail=='displacement':
   selected['vector_displacement']=dict(maps['height'])
  if mode=='triplanar':
   selected.pop('normal');selected.pop('coat_normal')
  p.write_text(json.dumps({'texture_sets':[{'name':'Test Material','maps':selected}]}))
  library=hou.node('/stage').createNode('materiallibrary')
  paths=build_materials(library,p,profile='cycles',texture_mode=mode,detail_mode=detail,offset_per_instance=mode!='auto')
  library.cook(force=True)
  assert not library.errors(),library.errors()
  stage=library.stage()
  mat=UsdShade.Material(stage.GetPrimAtPath(next(iter(paths.values()))))
  assert mat,(paths,stage.Flatten().ExportToString())
  assert mat.GetOutput('cycles:surface').HasConnectedSource()
  shaders=[UsdShade.Shader(prim) for prim in stage.Traverse() if prim.IsA(UsdShade.Shader)]
  assert all(s.GetIdAttr().Get().startswith('cycles_') for s in shaders)
  ids={s.GetIdAttr().Get() for s in shaders}
  assert 'cycles_image_texture' in ids
  if mode=='auto':
   for shader in shaders:
    if shader.GetIdAttr().Get()=='cycles_image_texture':
     assert list(shader.GetInput('tiles').Get())==[1001,1002]
  if detail=='displacement':
   assert 'cycles_vector_displacement' in ids
  assert mat.GetOutput('cycles:displacement').HasConnectedSource()
  assert ('cycles_bump' in ids)==(detail=='bump')
  assert ('cycles_normal_map' in ids)==(mode!='triplanar')
  print('PASS',mode,detail,len(shaders),'native shaders')
  before=library.children()
  try:build_materials(library,p,profile='cycles',texture_mode='hex')
  except RuntimeError:pass
  else:raise AssertionError('hex must fail')
  assert before==library.children()
  p.write_text(json.dumps({'texture_sets':[{'name':'Normals','maps':maps}]}))
  try:build_materials(library,p,profile='cycles',texture_mode='triplanar')
  except RuntimeError:pass
  else:raise AssertionError('triplanar tangent normals must fail')
  assert before==library.children()
  library.destroy()
print('PASS unsupported mode preserves existing materials')

hou.hda.installFile(str(root/'otls/automated_texture_builder.hda'))
controller=hou.node('/stage').createNode('j7s::automated_texture_builder::1.0')
assert 'cycles' in controller.parm('builder_profile').parmTemplate().menuItems()
controller.parm('builder_profile').set('cycles')
controller.updateParmStates()
assert controller.parm('surface_model').isDisabled()
print('PASS controller Cycles profile and disabled MaterialX surface model')

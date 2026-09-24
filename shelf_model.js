'use strict';
function normalizeShelf(data,fallbackName=''){
  const hasBins=data.matrix?.some(row=>row.some(cell=>cell!==null));
  return {...data,schemaVersion:data.schemaVersion??2,mode:data.mode??(hasBins?'complex':'simple'),name:data.name??fallbackName,contents:data.contents??'',keywords:data.keywords??''};
}

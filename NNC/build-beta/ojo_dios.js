// Vista "Ojo de Dios" NNC — cliente vanilla JS (sin librerías nuevas; usa el mapa Leaflet ya presente).
// Autoría: Lázaro López Paz, El Prat de Llobregat, Barcelona, España, con asistencia IA.
// Reglas: no inventa detecciones; nunca FANI; catálogo <= E2; silencio ADS-B = indeterminado; ω·R solo con R medida.
(function(){
  'use strict';
  const API = location.protocol === 'file:' ? 'http://127.0.0.1:8765' : '';
  const HKEY = 'nnc_ojo_hist';
  const $ = id => document.getElementById(id);
  const e = x => String(x==null?'':x).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const n = (x,d) => (x===''||x==null||!Number.isFinite(Number(x))) ? '—' : Number(x).toFixed(d);
  const hm = s => s ? String(s).slice(11,19) : '—';
  let ojoLayer = (typeof L!=='undefined' && typeof map!=='undefined') ? L.layerGroup() : null;
  let timer = null, auto = true, activo = false, ultimo = null;

  function fila(cells){ return '<tr>'+cells.map(c=>'<td>'+c+'</td>').join('')+'</tr>'; }
  function st(s){ return '<span class="st-'+e(s)+'">'+e(s)+'</span>'; }

  function params(){
    const q = new URLSearchParams();
    [['radio_km','fRadio'],['el_min_deg','fEl'],['alt_min_ft','fAmin'],['alt_max_ft','fAmax'],['edad_max_s','fEdad']]
      .forEach(([k,id])=>{ const v=$(id).value.trim(); if(v!=='') q.set(k,v); });
    return q.toString();
  }
  function histLocal(){ try { return JSON.parse(localStorage.getItem(HKEY)||'[]'); } catch(_) { return []; } }
  function guardarHist(v){
    const h = histLocal();
    const last = h[h.length-1];
    if (last && last.t_utc === v.generado_utc) return;
    h.push({t_utc:v.generado_utc, t_madrid:v.generado_madrid, grupos:v.grupos, avisos:(v.avisos||[]).length,
             sil:(v.silencio_adsb||[]).length, emax:v.evidencia_max_mostrada,
             adsb:(v.fuentes.adsb||{}).fuente||'', ok:Object.fromEntries(Object.entries(v.fuentes).map(([k,s])=>[k,!!s.ok]))});
    const cut = Date.now()-7*864e5;
    localStorage.setItem(HKEY, JSON.stringify(h.filter(r=>Date.parse(r.t_utc)>cut).slice(-200)));
  }
  function pintarHist(){
    const h = histLocal().slice().reverse().slice(0,10);
    $('ojoHist').innerHTML = h.length ? h.map(r=>fila([e(hm(r.t_madrid)), e(Object.entries(r.grupos||{}).map(([t,g])=>t+': '+Object.entries(g).map(([s,c])=>s+'='+c).join(',')).join(' · ')),
      e('avisos '+r.avisos+' · silencio '+r.sil+' · '+r.emax)])).join('') : fila(['<span class="dim">Sin historial local</span>']);
  }
  function pintarMapa(v){
    if (!ojoLayer) return;
    ojoLayer.clearLayers();
    (v.objetos||[]).forEach(o=>{
      if (!Number.isFinite(o.lat) || !Number.isFinite(o.lon)) return;
      const col = o.estado==='EXPLICADO' ? (o.tipo==='satelite_tle' ? '#f5c542' : '#3dd68c') : (o.estado==='no_explicado_pendiente' ? '#f5c542' : '#8ea0c4');
      L.circleMarker([o.lat,o.lon], {radius:o.tipo==='satelite_tle'?8:5, color:col, fillColor:col, fillOpacity:.85})
        .bindTooltip(e(o.id)+'<br>'+e(o.estado)+' · '+e((o.cadena||{}).excluido_por||'')+' · '+e((o.cadena||{}).evidencia||''))
        .addTo(ojoLayer);
    });
  }
  function pintar(v){
    ultimo = v;
    if (activo) cabecera(v);
    $('ojoT').textContent = 'generado '+hm(v.generado_madrid)+' (hora de Madrid) · '+v.calculo_s+' s';
    const det = $('ojoDet');
    det.className = 'ojo-banner'+((v.detecciones_opticas||[]).length?'':' vacio');
    det.innerHTML = (v.detecciones_opticas_nota ? e(v.detecciones_opticas_nota) : e(v.detecciones_opticas.length+' detecciones ópticas reales evaluadas'))+
      '<br>Evidencia máxima mostrada: <b>'+e(v.evidencia_max_mostrada)+'</b> · '+e(v.evidencia_nota)+'<br>FANI declarado: <b>no</b> (prohibido). Estación '+
      e(v.estacion.lat_deg)+', '+e(v.estacion.lon_deg)+' — '+e(v.estacion.coord_status);
    const av = v.avisos||[];
    $('ojoAvisos').className = av.length ? 'aviso' : 'okbox';
    $('ojoAvisos').innerHTML = av.length ? av.map(a=>e(a.tipo+' '+a.id+': residuo '+a.residuo_km+' km = '+a.n_sigma+'σ (σ='+a.sigma_km+' km) · '+a.estado+' · '+a.nota)).join('<br>')
      : e('Sin desviación medible (> '+v.modelo_incertidumbre.k_sigma+'σ). '+v.avisos_nota);
    $('ojoFuentes').innerHTML = Object.entries(v.fuentes).map(([k,s])=>fila([e(k), s.ok?'<span class="st-EXPLICADO">ok</span>':'<span class="err">fallo</span>',
      e(s.fuente||''), e('HTTP '+s.http_status), e('edad '+(s.edad_s===''||s.edad_s==null?'—':s.edad_s+' s')+(s.stale?' · caducada':'')+(s.descartado?' · '+s.descartado:''))])).join('');
    $('ojoGrupos').innerHTML = Object.entries(v.grupos).map(([t,g])=>fila([e(t), Object.entries(g).map(([s,c])=>st(s)+' '+c).join(' · ')])).join('') || fila(['<span class="dim">sin objetos</span>']);
    const iss = (v.objetos||[]).find(o=>o.tipo==='satelite_tle');
    if (iss){
      const d = iss.desviacion||{};
      $('ojoIss').innerHTML = fila(['estado', st(iss.estado)+' · '+e(iss.motivo_estado)])+
        fila(['az / el ahora', n(iss.az_deg,1)+'° / '+n(iss.el_deg,1)+'° '+(iss.sobre_horizonte?'(sobre horizonte)':'(bajo horizonte)')])+
        fila(['cadena', e(iss.cadena.excluido_por)+' · '+e(iss.cadena.resultado)+' · '+e(iss.cadena.evidencia)])+
        fila(['SGP4 vs wheretheiss', d.residuo_km!=null ? e(d.residuo_km+' km = '+d.n_sigma+'σ · medible: '+d.desviacion_medible) : e(d.motivo||'—')])+
        fila(['ω · R · v', 'ω '+e(iss.cinematica.omega_rad_s||'—')+' · R "'+e(iss.cinematica.R_m)+'" · v "'+e(iss.cinematica.v_tan_m_s)+'"']);
      $('ojoPases').innerHTML = (iss.pases_24h||[]).map(p=>fila([e(hm(p.rise_madrid)+'–'+hm(p.set_madrid)),
        e(p.clase)+(p.clase==='potencialmente_visible_optico'?'<br><span class="dim">'+e(hm(p.visible_start_madrid)+'–'+hm(p.visible_end_madrid)+' · máx '+p.visible_max_el_deg+'° · '+p.brillo)+'</span>'
          :'<br><span class="dim">'+e([].concat(p.motivos||[]).join(', '))+'</span>'),
        e('culm '+p.culm_el_deg+'° az '+p.culm_az_deg+'°')])).join('') || fila(['<span class="dim">sin pases ≥10° en 24 h</span>']);
    } else { $('ojoIss').innerHTML = fila(['<span class="err">ISS no disponible (TLE)</span>']); $('ojoPases').innerHTML=''; }
    const m = v.meteo||{};
    $('ojoMeteo').innerHTML = fila(['nubosidad', e(m.cloud_cover_pct)+' %'])+fila(['visibilidad', e(m.visibility_m===''||m.visibility_m==null?'—':m.visibility_m+' m')])+
      fila(['viento 10 m', e(m.wind_speed_10m+' '+(m.wind_speed_unit||'')+' · '+m.wind_direction_10m_deg+'°')])+fila(['hora modelo', e(m.api_time)+' · '+e(m.nota)]);
    const objs = (v.objetos||[]).filter(o=>o.tipo!=='satelite_tle');
    const orden = {'no_explicado_pendiente':0,'indeterminado':1,'EXPLICADO':2};
    objs.sort((a,b)=>(orden[a.estado]-orden[b.estado]) || ((a.dist_km||0)-(b.dist_km||0)));
    $('ojoObj').innerHTML = objs.length ? objs.slice(0,40).map(o=>{
      const c=o.cadena||{}, k=o.cinematica||{}, d=o.desviacion||{};
      return fila([e(o.id)+'<br><span class="dim">'+e(o.tipo)+'</span>',
        st(o.estado)+' · '+e(c.excluido_por||'')+' · '+e(c.evidencia||'')+'<br><span class="dim">'+n(o.dist_km,1)+' km · '+n(o.alt_ft,0)+' ft · el '+n(o.el_deg,1)+'°</span>',
        '<span class="dim">ω '+(k.omega_rad_s===''?'—':Number(k.omega_rad_s).toExponential(2)+' rad/s')+' · R "'+e(k.R_m)+'" · v_baliza '+n(o.v_baliza_m_s,0)+' m/s<br>desv: '+
          e(d.desviacion_medible===true?('SÍ '+d.n_sigma+'σ'):(d.desviacion_medible===false?('no ('+d.n_sigma+'σ)'):'indeterminado'))+'</span>']);
    }).join('') : fila(['<span class="dim">Sin objetos tras filtros ('+e(v.n_descartados)+' descartados)</span>']);
    const sil = v.silencio_adsb||[];
    $('ojoSil').innerHTML = (sil.length ? sil.slice(0,15).map(x=>fila([e(x.hex), st(x.estado), '<span class="dim">'+e(x.motivo)+'</span>'])).join('') : fila(['<span class="dim">Sin balizas perdidas desde el último snapshot</span>']))+
      (v.silencio_adsb_global && v.silencio_adsb_global.motivo ? fila([st('indeterminado'), e(v.silencio_adsb_global.motivo)]) : '');
    guardarHist(v); pintarHist(); pintarMapa(v);
  }
  async function cargar(){
    try {
      const r = await fetch(API+'/api/ojo?'+params(), {cache:'no-store'});
      const j = await r.json();
      if (!r.ok || !j.ok) throw new Error((j && (j.error+' '+(j.detalle||''))) || ('HTTP '+r.status));
      pintar(j);
    } catch(err) {
      $('ojoDet').className = 'ojo-banner vacio';
      $('ojoDet').innerHTML = '<span class="err">Ojo de Dios sin datos: '+e(err.message)+'</span><br>Arranca: <code>python ws_vivo.py</code> (con dependencias de ojo_de_dios) y abre http://127.0.0.1:8765/#ojo. Sin servidor no se muestra nada (no se inventa).';
    }
  }
  function cabecera(v){
    const a = (v.fuentes||{}).adsb||{};
    $('src').textContent = 'Ojo de Dios · en vivo · ADS-B '+(a.fuente||'—')+' · '+hm(v.generado_madrid)+' Madrid';
    $('src').className = 'pill '+(a.ok ? 'ok' : 'bad');
    $('nobj').textContent = (v.objetos||[]).length+' objetos (Ojo) · '+v.evidencia_max_mostrada;
    $('nalert').textContent = (v.avisos||[]).length+' avisos (desviación medible)';
  }
  function programar(){ clearInterval(timer); if (auto && activo) timer = setInterval(cargar, 30000); }
  function tab(cual){
    activo = cual==='ojo';
    window.__ojoActivo = activo;
    $('paneOjo').hidden = !activo; $('paneRadar').hidden = activo;
    $('tabOjo').classList.toggle('on', activo); $('tabRadar').classList.toggle('on', !activo);
    if (ojoLayer){ if (activo){ ojoLayer.addTo(map); if (typeof layer!=='undefined') map.removeLayer(layer); } else { map.removeLayer(ojoLayer); if (typeof layer!=='undefined') layer.addTo(map); } }
    if (activo){ if (ultimo) cabecera(ultimo); cargar(); history.replaceState(null,'','#ojo'); }
    else { history.replaceState(null,'',location.pathname+location.search); if (typeof pillFuente==='function') pillFuente(radarSrc); if (typeof draw==='function') draw(current); }
    programar();
  }
  $('tabOjo').onclick = ()=>tab('ojo');
  $('tabRadar').onclick = ()=>tab('radar');
  $('bOjo').onclick = cargar;
  $('bOjoAuto').onclick = ()=>{ auto=!auto; $('bOjoAuto').classList.toggle('on', auto); programar(); };
  $('bHistSrv').onclick = async ()=>{
    try { const r = await fetch(API+'/api/ojo/historial?n=10'); const j = await r.json();
      $('ojoHist').innerHTML = (j.historial||[]).slice().reverse().map(x=>fila([e(hm(x.t_madrid)), e(JSON.stringify(x.grupos)), e('avisos '+(x.avisos||[]).length+' · '+x.evidencia_max)])).join('') || fila(['<span class="dim">JSONL vacío</span>']);
    } catch(err){ $('ojoHist').innerHTML = fila(['<span class="err">'+e(err.message)+'</span>']); }
  };
  pintarHist();
  if (location.hash === '#ojo') tab('ojo');
  window.__ojo = {cargar, tab, ultimo:()=>ultimo};
})();

"""Aplicación de definiciones revisadas y evaluación con evidencia complementaria."""
from decimal import Decimal
from calificar import (calificar_indicador, dependencias, filas_por_año, numero,
                       normalizar, tema_sin_informacion)
from evidencia_complementaria import poblacion, tasas_comparables


def numeric(value):
    result = numero(str(value))
    return result if result is not None and result >= 0 else None


def conteo(section, year, scope='municipal', column='Total'):
    rows = [r for r in filas_por_año(section, scope).get(year, []) if column in r['celdas']]
    return numeric(rows[0]['celdas'][column]) if len(rows) == 1 else None


def tiene_respuesta(section, years):
    """Cero y No son respuestas: no autorizan un candado de falta de respuesta."""
    unknown = {'', '-', '--', 'n/d', 'nd', 'n.a.', 'n/a', 'no disponible',
               'no identificado', 'no se sabe', 'sin informacion', 'sin datos'}
    return any(normalizar(str(value)) not in unknown
               for year in years for row in filas_por_año(section).get(year, [])
               for column, value in row['celdas'].items() if column != 'Año')


def provisional(number, section, years, obs, motivo, definitions):
    level, confidence, basis = None, 'no_estimable', []
    if number == 10:
        topics = set()
        for row in filas_por_año(section).get(years[-1], []) if years else []:
            topic = row['celdas'].get('Tema', '')
            if not tema_sin_informacion(topic) and numeric(row['celdas'].get('Total')) not in (None, 0):
                topics.add(topic)
        if topics:
            basis = sorted(topics)
            # Sin homologación y universo no se convierte el conteo de rótulos en nivel.
    if number == 14 and years:
        counts = [conteo(section, y) for y in years]
        if all(v is not None for v in counts):
            basis = [f'{y}: {v} cámaras reportadas' for y, v in zip(years, counts)]
            if all(v > 0 for v in counts) and all(a <= b for a, b in zip(counts, counts[1:])):
                level, confidence = 3, 'baja'
            elif any(v == 0 for v in counts) and any(v > 0 for v in counts):
                level, confidence = 2, 'baja'
    if number == 15 and len(years) >= 2:
        counts = [conteo(section, y, column='Llamadas procedentes') for y in years[-2:]]
        if all(v is not None for v in counts) and all(obs.get(str(y), {}).get('registro_municipal') is True for y in years[-2:]):
            level, confidence = 3, 'baja'
            basis = [f'{y}: {v} llamadas procedentes' for y, v in zip(years[-2:], counts)]
    return {'nivel_indicativo': level, 'base': basis, 'confianza': confidence,
            'falta': motivo, 'computa_en_agregacion': False,
            'regla': definitions['interpretacion_provisional']['reglas_por_ficha'].get(str(number),
                     'Describir la información disponible sin asignar un nivel no acreditado.')}


def evaluar(sections, rules, mappings, periods, complemento):
    """Ambos periodos comparten reglas y verificaciones; el renderizador recalcula esto."""
    definitions = rules['definiciones_config']
    evaluations = {}
    for period in ('general', 'ultimo_periodo'):
        results = {}
        for section, ficha in zip(sections, rules['fichas']):
            n = section['numero']
            target = periods['ultimo_periodo']['por_indicador'][str(n)] if period == 'ultimo_periodo' else None
            result = calificar_indicador(section, ficha, period, mappings, años_objetivo=target)
            years = result['años_evaluados']
            obs = complemento.get('observaciones', {}).get(str(n), {})
            entries = [obs.get(str(y), {}) for y in years]
            operational = complemento.get('observaciones', {}).get('4', {})
            unavailable = n >= 4 and any(operational.get(str(y), {}).get('institucion_propia') is False for y in years)
            if unavailable:
                result.update(puntaje=None, estado_dato='no_aplicable',
                              motivo='Sin institución municipal propia en parte del periodo; requiere un universo de evaluación específico.')
            elif years and n in (2, 3, 4, 5, 7, 9, 10, 14, 15, 18):
                result = revisar_ficha(n, section, result, years, entries, complemento, definitions)
            if (not unavailable and result['puntaje'] is None and years
                    and not tiene_respuesta(section, years)
                    and all(e.get('revision') == 'verificada' and e.get('sin_respuesta_municipal_acreditada') is True for e in entries)):
                result.update(puntaje=1, sin_respuesta_municipal=True,
                              criterio_aplicado='Ausencia de respuesta municipal acreditada en todo el periodo.')
                result.pop('motivo', None)
            if result['puntaje'] is None:
                result.setdefault('estado_dato', 'pendiente')
                result['valoracion_provisional'] = provisional(n, section, years, obs,
                    result.get('motivo', 'Falta evidencia suficiente.'), definitions)
                if unavailable:
                    result['valoracion_provisional'].update(nivel_indicativo=None, confianza='no_estimable', base=[])
            else:
                result['estado_dato'] = 'reportado'
            results[n] = result
        dependencias(results)
        for n, result in results.items():
            if result['puntaje'] is not None:
                result['estado_dato'] = 'reportado'
                result.pop('valoracion_provisional', None)
            else:
                result.setdefault('estado_dato', 'pendiente')
                result.setdefault('valoracion_provisional', provisional(n, sections[n-1], result['años_evaluados'],
                    complemento.get('observaciones', {}).get(str(n), {}), result.get('motivo', 'Dependencia pendiente.'), definitions))
        evaluations[period] = results
    return evaluations


def revisar_ficha(n, section, old, years, entries, data, definitions):
    result = {key: value for key, value in old.items() if key in (
        'años_observados', 'años_evaluados', 'cobertura', 'cobertura_temporal_insuficiente',
        'años_faltantes_por_ambito')}
    result['puntaje'] = None
    def missing(message):
        result['motivo'] = message
        return result
    def scored(value, metrics=None):
        result.update(puntaje=value, criterio_aplicado=f'Ficha {n}, integración 2.3, nivel {value}')
        result.pop('motivo', None)
        if metrics is not None: result['metricas_revisadas'] = metrics
        return result
    if old.get('cobertura_temporal_insuficiente') and n != 15:
        return missing('Cobertura temporal insuficiente para aplicar la ficha revisada.')
    if not all(e.get('revision') == 'verificada' for e in entries):
        return missing(f'Falta confirmar la definición y procedencia de la ficha {n} en todos los años evaluados.')
    if n == 2:
        if not all(e.get('universo') == 'personal_unidad_pc' and e.get('conteo_personas') == 'unico' for e in entries):
            return missing('Confirmar capacitación al personal de la unidad y conteo único; no mezclar difusión a población.')
        return old
    if n in (5, 7, 10):
        required = {5: 'aprobatorias_vigentes', 7: 'cup_vigente', 10: 'capacitacion_sin_profesionalizacion'}[n]
        if not all(e.get('universo') == 'corporaciones_policiales' and e.get('definicion') == required for e in entries):
            return missing('Confirmar el universo policial y la definición del porcentaje; no inferirlos del encabezado Total o Porcentaje.')
        return old
    if n == 3:
        groups = definitions['normalizacion_proteccion_civil']['grupos']
        coverage = []
        rows = filas_por_año(section)
        for year, e in zip(years, entries):
            captured = e.get('grupos_captados', [])
            if (not captured or len(captured) != len(set(captured)) or not set(captured) <= set(groups)
                    or e.get('catalogo_completo') is not True):
                return missing('Falta el catálogo y sus grupos efectivamente captados en la edición.')
            found = set()
            for row in rows.get(year, []):
                topic = row['celdas'].get('Tema impartido', '')
                if tema_sin_informacion(topic): return missing('Hay temas sin identificar.')
                for group in captured:
                    if any(normalizar(t) in normalizar(topic) for t in groups[group]): found.add(group)
            if not found and e.get('ausencia_temas_acreditada') is not True:
                return missing('No hay temas núcleo identificados; confirmar ausencia, no inferirla de rótulos sin homologar.')
            coverage.append({'anio': year, 'captados': captured, 'acreditados': sorted(found),
                             'proporcion': str(Decimal(len(found)) / len(captured))})
        ratio = sum(Decimal(c['proporcion']) for c in coverage) / len(coverage)
        risk = all('identificacion_y_analisis_de_riesgos' in c['acreditados'] for c in coverage)
        level = 5 if ratio >= Decimal('.8') and risk else 4 if ratio >= Decimal(2)/3 else 3 if ratio >= Decimal(1)/3 else 2 if ratio > 0 else 1
        return scored(level, coverage)
    if n == 4:
        rates = []
        staff = []
        for y, e in zip(years, entries):
            p, total = poblacion(data, y), numeric(e.get('personal_policial'))
            if not p or total is None: return missing('Falta población documentada o personal de corporaciones policiales.')
            rates.append(total * 1000 / Decimal(str(p['valor'])))
            staff.append(total)
        average = sum(rates) / len(rates)
        above = [v >= Decimal('1.8') for v in rates]
        if all(above): score = 5
        elif len(above) >= 2 and all(above[-2:]) and sum(above)*2 >= len(above): score = 4
        elif Decimal('1.2') <= average < Decimal('1.8') or above[-1]: score = 3
        elif Decimal('.8') <= average < Decimal('1.2'): score = 2
        elif average < Decimal('.8'): score = 1
        else: return missing('La combinación de tasas no está cubierta por los umbrales del benchmark.')
        if min(staff) < 15: score = min(score, 4)
        return scored(score, {str(y):str(v) for y,v in zip(years,rates)})
    if n == 9:
        measures = []
        for e in entries:
            staff = numeric(e.get('personal_policial'))
            values = [numeric(e.get(k)) for k in ('chalecos', 'radios', 'menos_letal')]
            if (staff in (None,0) or any(v is None for v in values)
                    or e.get('naturaleza_del_dato') != 'asignado_al_cierre'):
                return missing('Acreditar equipo asignado al cierre, personal policial y tres conteos comparables.')
            measures.append((values[0]/staff,values[1]/staff,values[2]))
        complete = [c>=1 and r>=Decimal('.5') and l>0 for c,r,l in measures]
        if all(complete): score=5
        elif len(complete)>=2 and all(complete[-2:]): score=4
        elif all(c==r==l==0 for c,r,l in measures): score=1
        elif all(c<Decimal('.5') for c,r,l in measures): score=2
        elif all(c>=Decimal('.5') and (r<Decimal('.5') or l==0) for c,r,l in measures): score=3
        else: return missing('La combinación de dotaciones requiere interpretación: no se interpolan niveles.')
        return scored(score, [[str(v) for v in row] for row in measures])
    if n == 14:
        pairs=[];counts=[]
        for y,e in zip(years,entries):
            a,b=conteo(section,y),conteo(section,y,'estatal')
            if a is None or b is None or e.get('universo') != 'camaras_en_servicio':
                return missing('Confirmar conteos municipales y estatales de cámaras en servicio.')
            pair=tasas_comparables(data,y,a,b)
            if pair is None:return missing('Faltan poblaciones municipal y estatal de la misma serie, fecha y método.')
            pairs.append(pair);counts.append(a)
        above=[a>=b for a,b in pairs]
        if not any(counts):score=1
        elif sum(c>0 for c in counts)==1 and len(counts)>1:score=2
        elif all(c>0 for c in counts) and all(above) and all(a[0]<=b[0] for a,b in zip(pairs,pairs[1:])):score=5
        elif len(above)>=2 and all(above[-2:]):score=4
        elif any(c>0 for c in counts) and any(a<b for a,b in pairs):score=3
        else:return missing('Trayectoria de cámaras no cubierta inequívocamente por los criterios.')
        return scored(score, {str(y):[str(v) for v in pair] for y,pair in zip(years,pairs)})
    if n == 15:
        # El comparador histórico exigía serie estatal; ya no es requisito del registro municipal.
        result.pop('años_faltantes_por_ambito', None)
        result['cobertura_temporal_insuficiente'] = False
        if not all(e.get('registro_municipal') is True for e in entries):
            return missing('Confirmar competencia municipal y universo del registro de llamadas.')
        counts=[conteo(section,y,column='Llamadas procedentes') for y in years]
        if any(e.get('ausencia_registro_acreditada') is True and v not in (None, 0) for v,e in zip(counts,entries)):
            return missing('Se declaró ausencia de registro junto a un conteo positivo; conciliar la evidencia.')
        if all(e.get('ausencia_registro_acreditada') is True for e in entries):return scored(1)
        if any(v is None for v in counts):
            if all(v is not None for v in counts[-2:]) and len(counts)>=2 and all(v is not None or e.get('ausencia_registro_acreditada') is True for v,e in zip(counts,entries)):
                if any(not poblacion(data,y) for y,v in zip(years,counts) if v is not None):
                    return missing('El registro parcial requiere población para las observaciones disponibles.')
                return scored(3)
            if len(entries)>=2 and all(e.get('ausencia_registro_acreditada') is True for e in entries[-2:]) and any(v is not None for v in counts[:-2]):return scored(2)
            return missing('Faltan conteos; una celda vacía no acredita ausencia del registro.')
        rates=[]
        for y,count in zip(years,counts):
            p=poblacion(data,y)
            if not p:return missing('Falta población documentada para describir llamadas por mil habitantes.')
            rates.append(count*1000/Decimal(str(p['valor'])))
        score=5 if all(e.get('meta_respuesta_cumplida') is True and e.get('meta_respuesta') for e in entries) else 4
        percentages=[conteo(section,y,column='Porcentaje') for y in years]
        if any(v == 100 for v in percentages) or any(e.get('dato_dudoso') is True for e in entries):score=min(score,3)
        return scored(score,{str(y):str(v) for y,v in zip(years,rates)})
    if n == 18:
        ratios=[]
        for e in entries:
            values=[numeric(e.get(k)) for k in ('personas_mp','delitos_municipales','personas_mp_estatal','delitos_estatales')]
            if any(v is None for v in values) or values[1]==0 or values[3]==0 or e.get('incidencia_comparable') is not True:
                return missing('Separar personas ante MP de justicia cívica y documentar incidencia comparable; población no sustituye delitos.')
            local,state=values[0]/values[1],values[2]/values[3]
            if state==0:return missing('Razón estatal cero; no comparar mediante división.')
            ratios.append(local/state)
        if all(v>=1 for v in ratios):
            verified=all(e.get('revision_derechos')=='sin_recomendaciones_documentada' and e.get('control_uso_fuerza')=='revisado' for e in entries)
            stable=all(a<=b for a,b in zip(ratios,ratios[1:]))
            score=5 if verified and stable and max(ratios)<=2 else 4
        elif all(Decimal('.75')<=v<1 for v in ratios):score=3
        elif all(v<Decimal('.75') for v in ratios):score=2
        else:return missing('Las razones cruzan umbrales; la ficha no define una combinación temporal inequívoca.')
        return scored(score,{str(y):str(v) for y,v in zip(years,ratios)})
    return result

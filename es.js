/* Spanish for Safe Routes to School.
 *
 * `s` holds replacement HTML for every element in index.html that carries a
 * data-t key (English stays in the HTML and is captured before the first
 * switch). `d` holds the strings app.js builds at run time, with {name}
 * placeholders that t() fills in. Adding a third language means one more file
 * shaped like this one and one more entry in the toggle. */
window.LANGS = window.LANGS || {};
window.LANGS.es = {
  name: 'Español',
  s: {
    'kicker': 'Los Ángeles / 2020&ndash;2024',
    'h1sub': 'a la escuela',
    'tagline': 'Indicaciones para caminar hechas a partir de dónde asaltan de verdad a los estudiantes, y no solo de la distancia.',
    'tab.route': 'Ruta',
    'tab.school': 'Escuela',
    'tab.method': 'Método',

    'intro.h': 'Cómo usar esto',
    'intro.1': 'Elige la <b>escuela</b> a la que caminas.',
    'intro.2': 'Escribe la <b>dirección o el cruce de calles</b> de donde sales, o haz clic en cualquier punto del mapa.',
    'intro.3': 'Compara las <b>tres rutas</b> que te ofrece y elige una.',
    'intro.demo': 'Muéstrame un ejemplo',

    'walk.h': 'La caminata',
    'walk.school': 'Escuela',
    'walk.from': 'Saliendo de',
    'walk.note': 'Dos calles que se cruzan, como <b>Hauser &amp; Venice</b>, se encuentran en este dispositivo y funcionan sin conexión. Las direcciones completas se buscan en OpenStreetMap. También puedes hacer clic en el mapa para marcar un punto.',
    'walk.locate': 'Usar mi ubicación',
    'clear': 'Empezar de nuevo',
    'ph.school': 'Escribe el nombre de la escuela',
    'ph.origin': 'Dirección, o cruce como Hauser & Venice',

    'when.h': 'Hora del día',
    'when.0': 'Mañana', 'when.0s': '5am a 10am',
    'when.1': 'Tarde', 'when.1s': '10am a 5pm',
    'when.2': 'Noche', 'when.2s': '5pm a 5am',

    'mode.h': 'Cómo llegar',
    'mode.foot': 'A pie', 'mode.foots': 'todo el camino',
    'mode.bus': 'Autobús o tren', 'mode.buss': 'caminar a una parada',
    'mode.note': 'Ir en autobús cubre distancia sin ponerte en la calle, así que un viaje en autobús suele tener menos exposición aunque tarde más.',

    'go': 'Comparar rutas',

    'cards.h': 'Tres opciones',
    'cards.note': 'La exposición es el riesgo promedio de las cuadras que caminas, de 0 a 100, comparado con todas las cuadras de Los Ángeles a esa hora. Menos es más tranquilo.',
    'why.h': 'Por qué esta ruta',
    'hours.h': 'Misma ruta, <b>otra hora</b>',
    'turns.h': 'Calle por calle',

    'keep.h': 'Guarda esta ruta',
    'keep.copy': 'Copiar un enlace',
    'keep.print': 'Imprimir una tarjeta',
    'keep.report': 'Reportar un problema con esta ruta',
    'keep.note': 'El enlace abre este mismo viaje en cualquier teléfono. La tarjeta es para un estudiante que no tiene uno: las calles, en orden, en una sola hoja.',

    'layers.h': 'Capas del mapa',
    'layers.risk': 'Riesgo',
    'layers.schools': 'Escuelas',

    'rc.h': 'Informe por escuela',
    'rc.p': 'Una sola ruta le dice a un solo estudiante qué hacer. Esto califica cada dirección desde la que un estudiante podría llegar a la escuela, que es la versión con la que un director o un concejal puede actuar.',
    'rc.school': 'Escuela',
    'rc.run': 'Calificar cada acceso',
    'rc.note': 'Envía a un caminante hacia la escuela desde 16 puntos cardinales a unos 1.2 km, y ordena los accesos según lo que atraviesan.',
    'rc.th.from': 'Desde', 'rc.th.walk': 'Caminata', 'rc.th.exp': 'Exposición',

    'emb.h': 'Ponlo en el sitio web de tu escuela',
    'emb.p': 'Pega esto donde una página acepte HTML. Abre el planificador con tu escuela ya elegida, así que el estudiante solo tiene que escribir de dónde sale.',
    'emb.copy': 'Copiar el código',
    'emb.note': 'También funciona como enlace normal, para un boletín o un mensaje a las familias.',

    'm.problem.h': 'El problema',
    'm.problem.fig': 'Niños y jóvenes de 10 a 18 años asaltados en las calles de Los Ángeles en horario de ida y vuelta a la escuela entre 2020 y 2024. Es el 56% de los 1,838 robos a menores de esa edad, dentro de unas cinco horas del día.',
    'm.problem.1': 'Esos robos se repiten en lugares concretos, y cada uno de esos lugares ya está en los registros públicos. Lo que ninguna app de mapas hace es rodearlos.',
    'm.problem.2': 'El programa federal Safe Routes to School existe desde 1971 y trata casi solo de autos: cruces peatonales, topes, guardias de cruce. Pregúntale a un estudiante de Los Ángeles qué le preocupa al caminar a casa y el tráfico rara vez es la respuesta.',

    'm.meas.h': 'Lo que medimos',
    'm.meas.1': 'Separar los incidentes por hora del día solo significa algo cuando divides entre lo que dura cada ventana. La noche cubre 12 horas y parecería la peor solo por ser la más larga. Por hora:',
    'm.meas.th.w': 'Ventana', 'm.meas.th.i': 'Incidentes', 'm.meas.th.h': 'Por hora',
    'm.meas.r0': 'Mañana, 5am a 10am',
    'm.meas.r1': 'Tarde, 10am a 5pm',
    'm.meas.r2': 'Noche, 5pm a 5am',
    'm.meas.2': 'La caminata de regreso por la tarde es la peor hora del día de un estudiante, peor hora por hora que después de oscurecer. Es la misma ventana de 2pm a 6pm que señala la cifra de robos. No la estábamos buscando.',

    'm.data.h': 'De dónde salen los datos',
    'm.data.1': '<strong>85,634 incidentes violentos</strong> del <a href="https://data.lacity.org/Public-Safety/Crime-Data-from-2020-to-Present/2nrs-mtv8" target="_blank" rel="noopener">registro de delitos del LAPD</a>, de 2020 a 2024.',
    'm.data.2': '<strong>128,534 farolas</strong> de la <a href="https://maps.lacity.org/lahub/rest/services/Bureau_of_Street_Lighting/MapServer" target="_blank" rel="noopener">Oficina de Alumbrado Público de LA</a>.',
    'm.data.3': '<strong>668 escuelas</strong> del directorio del <a href="https://www.cde.ca.gov/ds/si/ds/pubschls.asp" target="_blank" rel="noopener">Departamento de Educación de California</a>.',
    'm.data.4': '<strong>18,473 km de calles transitables a pie</strong> de <a href="https://www.openstreetmap.org" target="_blank" rel="noopener">OpenStreetMap</a>, divididas en 431,599 cuadras.',
    'm.data.5': '<strong>5,395 paradas de autobús y tren</strong> de los <a href="https://developer.metro.net/gtfs-schedule-data/" target="_blank" rel="noopener">datos GTFS de LA Metro</a>, con tiempos de viaje y frecuencias.',

    'm.threw.h': 'Lo que descartamos',
    'm.threw.1': 'El archivo bruto del LAPD tiene cerca de un millón de registros. Nos quedamos solo con los delitos que amenazan a alguien que camina por la calle: robo, agresión, amenazas, mostrar un arma. Un convertidor catalítico robado no dice nada sobre si un niño está seguro en esa cuadra.',
    'm.threw.2': 'Un segundo filtro conserva solo los incidentes ocurridos en espacio público: calle, banqueta, callejón, parada de autobús, parque, paso a desnivel. Ese filtro descarta unos <strong>81,000 registros</strong> ocurridos bajo techo. La violencia doméstica es grave, y también es cierto que no es un peligro de pasar caminando frente a un edificio, así que contarla habría marcado cuadras residenciales normales como peligrosas para caminar.',

    'm.score.h': 'Cómo se califica una cuadra',
    'm.score.1': 'Cada incidente que sobrevive se pondera por su gravedad, por qué tan reciente fue (decaimiento exponencial con una vida media de 2.5 años) y por si la víctima era menor de edad. <strong>Los delitos contra menores cuentan triple</strong>, porque un delito contra alguien de 13 años dice más sobre el riesgo para alguien de 13 años que un delito contra un adulto.',
    'm.score.2': 'Los incidentes se extienden luego como núcleos gaussianos con un ancho de 120 m. Elegimos 120 m para igualar la imprecisión con que el LAPD registra las ubicaciones, no para sugerir que sabemos más que eso. Cada cuadra se muestrea cada 25 m, se califica y se ordena frente a todas las demás, así que 90 significa que la cuadra es peor que el 90% de Los Ángeles a esa hora.',
    'm.score.3': 'Las farolas le quitan a una cuadra hasta un 35% de su puntuación, con un tope para que una cuadra bien iluminada en una zona mala nunca parezca tranquila. Las avenidas anchas reciben una penalización; los senderos peatonales, un pequeño crédito.',

    'm.route.h': 'Cómo se elige la ruta',
    'm.route.1': 'El ruteo es A*, minimizando <code>longitud &times; (1 + &lambda; &middot; riesgo<sup>1.5</sup>)</code>. Las tres opciones que recibes son la misma búsqueda con tres valores de &lambda;. El exponente 1.5 tolera cuadras un poco elevadas y evita con firmeza las realmente malas. Una penalización lineal da rutas blandas que esquivan todo un poquito.',
    'm.route.2': 'Cada multiplicador de tramo es al menos 1, así que la distancia en línea recta nunca sobreestima lo que falta por caminar. La heurística es admisible y la ruta es demostrablemente la más barata, no una aproximación. <code>validate.py</code> lo comprueba contra Dijkstra en pares aleatorios y los costos salen idénticos.',
    'm.route.3': 'Ir en autobús se califica distinto: los minutos a bordo son minutos fuera de la calle, así que no tienen exposición alguna. Esperar sí la tiene. Un minuto en una parada se cobra como 80 m de caminata en esa cuadra, porque quedarse parado en una esquina mala no es un lugar seguro.',
    'm.route.4': 'Todo corre en este navegador. El grafo calificado se construye fuera de línea y se envía como un binario de 5 MB, así que no hay servidor detrás de esta página ni costo por mantenerla. Una vez cargada, sigue funcionando sin conexión.',

    'm.sdg.h': 'Objetivos de desarrollo',
    'm.sdg.11': '<b>Ciudades y comunidades sostenibles</b><span>La meta 11.2 pide transporte seguro con atención a la niñez. La meta 11.7 pide espacio público seguro.</span>',
    'm.sdg.4': '<b>Educación de calidad</b><span>La meta 4.a pide entornos de aprendizaje seguros. Un trayecto que un niño teme hacer lo deja fuera de la escuela.</span>',
    'm.sdg.16': '<b>Paz, justicia e instituciones sólidas</b><span>La meta 16.2 pide el fin de la violencia contra la niñez, aquí usando registros que esas instituciones ya publican.</span>',
    'm.sdg.10': '<b>Reducción de las desigualdades</b><span>Los estudiantes que cargan con este riesgo son los que no tienen auto ni quien los lleve. Para ellos se trazan estas rutas.</span>',

    'm.next.h': 'Dónde corre después',
    'm.next.1': 'Un solo recuadro de coordenadas en <code>config.py</code> es lo único específico de Los Ángeles aquí. El proceso necesita registros de incidentes geolocalizados, ubicaciones de escuelas y OpenStreetMap, que ya cubre el planeta. Chicago, Nueva York, Seattle, Denver, Austin, Baltimore, Toronto y Londres publican datos de incidentes con una forma compatible, así que apuntar esto a una de ellas es configuración, no una reescritura.',

    'm.limits.h': 'Lo que esto no puede decirte',
    'm.limits.1': '<strong>El delito reportado no es todo el delito.</strong> Las tasas de denuncia varían entre barrios y con el estatus migratorio, así que una puntuación baja refleja en parte quién llama a la policía.',
    'm.limits.2': '<strong>Las ubicaciones son aproximadas.</strong> El LAPD redondea las coordenadas para proteger a las víctimas, y por eso el modelo suaviza sobre 120 m.',
    'm.limits.3': '<strong>Los datos terminan en diciembre de 2024</strong>, cuando el LAPD cambió a un nuevo sistema de registros. Son completos y estables, y no están en vivo.',
    'm.limits.4': '<strong>Las puntuaciones son relativas a Los Ángeles.</strong> Un 20 significa tranquilo para los estándares de esta ciudad.',
    'm.limits.5': '<strong>Esto es una segunda opinión sobre una caminata.</strong> Una calle vacía que al modelo le gusta puede ser peor que una concurrida que califica mal, y tú sabes cosas de tu propio barrio que una tabla de delitos no registra.',

    'm.about.h': 'Sobre este proyecto',
    'm.about.1': 'Hecho por tres estudiantes de Los Ángeles. Quedó en tercer lugar en el reto Code for Transportation de Young Coders’ Sphere en agosto de 2026, y ha seguido creciendo desde entonces: español, autobús y tren, un informe por escuela, tarjetas para imprimir y una versión que funciona sin conexión. El código está abierto en <a href="https://github.com/safe-routes-la/safe-routes-la.github.io" target="_blank" rel="noopener">github.com/safe-routes-la</a>.',

    'hint': 'Acércate para ver cómo califica cada cuadra',
    'lg.h': 'Riesgo por cuadra',
    'lg.calm': 'más tranquilo', 'lg.worst': 'lo peor de LA',
    'lg.chosen': 'Ruta elegida', 'lg.short': 'Ruta más corta',
    'lg.drawn': 'cuadras dibujadas',
    'boot.msg': 'Cargando la red de calles',
  },

  d: {
    'win.0': 'mañana', 'win.1': 'tarde', 'win.2': 'noche',
    'clock.0': '5am a 10am', 'clock.1': '10am a 5pm', 'clock.2': '5pm a 5am',
    'compass': 'N,NNE,NE,ENE,E,ESE,SE,SSE,S,SSO,SO,OSO,O,ONO,NO,NNO',

    'toast.nostreet': 'No hay una calle transitable cerca de ese punto.',
    'toast.same': 'Ese punto de salida ya está en la escuela.',
    'toast.noroute': 'Ninguna ruta a pie conecta esos puntos.',
    'toast.nobus': 'Ningún autobús o tren conecta esos puntos en un solo viaje. Mostrando la caminata.',
    'toast.rcnostreet': 'Esa escuela no está cerca de una calle transitable.',
    'toast.rcnone': 'No se pudo llegar a esa escuela desde ninguna dirección.',
    'toast.copyfail': 'No se pudo copiar. La barra de direcciones tiene el enlace.',
    'toast.print': 'Elige una ruta primero.',
    'ac.none': 'No se encontró nada con eso',
    'ac.busy': 'Buscando…',
    'ac.offline': 'Sin conexión: no se pueden buscar direcciones. Escribe dos calles que se cruzan, o toca el mapa.',
    'ac.xstreet': 'cruce de calles',
    'geo.wait': 'Buscando tu ubicación…',
    'geo.here': 'Mi ubicación',
    'toast.nogeo': 'Este navegador no comparte la ubicación.',
    'toast.geoout': 'Estás fuera del área del mapa, que cubre el centro de Los Ángeles.',
    'toast.geofail': 'No se pudo obtener tu ubicación. Revisa el permiso del navegador.',

    'mode.none': 'Nada a menos de 900 m a pie de ambos extremos comparte una ruta, así que estas son opciones a pie. Los transbordos quedan fuera: cada cambio añade otra espera.',
    'mode.found': 'Ir en autobús cubre distancia sin ponerte en la calle. Esperar no, así que un minuto en una parada se cobra como {w} m de caminata en ese lugar.',

    'opt.short': 'Más corta', 'opt.shortH': 'lo que te da una app de mapas',
    'opt.mid': 'Equilibrada', 'opt.midH': 'más calma por cada paso extra',
    'opt.safe': 'Más segura', 'opt.safeH': 'la menor exposición disponible',
    'opt.walk': 'Caminar todo el camino', 'opt.walkH': 'sin autobús, para comparar',
    'opt.route': 'Ruta {r}',
    'opt.then': ' y luego ',
    'opt.rideH': '{n} min a bordo, {d} a pie',
    'opt.change': ', un cambio',

    'card.less': '{cut}% menos exposición',
    'card.min': '{n} min',
    'card.sub': '{d} a pie / {e}',

    'why.same': 'El camino más corto aquí es también el más tranquilo que el modelo encuentra, así que no hay nada que intercambiar.',
    'why.skips': 'Evita <b>{len}</b> de <span class="st">{st}</span>, que califica <b>{n}</b> a esta hora.',
    'why.along': 'Va por <span class="st">{st}</span> en su lugar, con <b>{n}</b>.',
    'why.samelen': 'Sale con la misma longitud.',
    'why.costm': 'Te cuesta <b>{m} m</b>, menos de un minuto a pie.',
    'why.cost1': 'Te cuesta <b>1 minuto</b>.',
    'why.costn': 'Te cuesta <b>{n} minutos</b>.',
    'why.drops': 'La exposición total baja <b>{cut}%</b>.',
    'unnamed': 'un camino sin nombre',
    'unnamed.turn': 'camino sin nombre',

    'why.t.ride': 'toma <b>{r}</b> durante <b>{n} min</b>',
    'why.t.ridex': 'toma <b>{r}</b> durante <b>{n} min</b> con un cambio en <span class="st">{stop}</span>',
    'why.t.main': 'Camina <b>{d1}</b> hasta <span class="st">{stop}</span>, espera unos <b>{w} min</b> en total, luego {ride}, y camina <b>{d2}</b> al final.',
    'why.t.only': 'Solo <b>{d}</b> de este viaje ocurre en la calle.',
    'why.t.drops': 'Frente a caminar todo el camino, la exposición baja <b>{cut}%</b>.',
    'why.t.flat': 'Es casi la misma exposición que caminarlo, así que toma la que te convenga.',

    'hours.now': '\u00B7 ahora',
    'hours.note': 'Este mismo viaje tiene más exposición en la {win} ({clock}). Cambiar la ventana arriba repite la búsqueda, que muchas veces devuelve una ruta distinta.',

    'turn.board': 'Sube a {r} en {stop}',
    'turn.wait': 'espera {n} min',
    'turn.ride': 'Viaja {n} paradas',
    'turn.off': 'Baja en {stop}',
    'turn.xfer': 'Camina a {stop} para cambiar',
    'stop.a': 'una parada',
    'mk.board': 'Sube', 'mk.off': 'Baja', 'mk.change': 'Cambia aquí',
    'pin.start': 'Salida',
    'dest.custom': 'Destino elegido',

    'rc.title': '{n} accesos / <b>{win}</b>',
    'rc.ratio': 'Llegar a {school} desde el <b>{worst}</b> significa atravesar <b>{ratio} veces</b> la exposición del acceso más tranquilo, desde el <b>{best}</b>.',
    'rc.same': 'Llegar a {school} desde el <b>{worst}</b> significa más o menos la misma exposición que el acceso más tranquilo, desde el <b>{best}</b>.',
    'rc.tail': 'Ahí es donde un guardia de cruce, una solicitud de alumbrado o un grupo de caminata harían más bien.',

    'when.now': 'Son las {clock}, así que está seleccionada la {win}. Cámbiala para planear otra caminata.',
    'when.restored': 'Restaurado desde un enlace compartido.',
    'preset': 'Esta página está preparada para <b>{school}</b>. Escribe de dónde sales. <a href="{href}">¿No es tu escuela?</a>',
    'share.done': 'Enlace copiado',
    'emb.done': 'Código copiado',

    'net.saved': '<b>Guardado en este dispositivo.</b> Funciona sin conexión.',
    'net.off': '<b>Sin conexión.</b> Las rutas siguen funcionando; el mapa muestra las calles sin nombres.',

    'boot.build': 'Construyendo el grafo de rutas',
    'boot.sub': '{n} incidentes / {km} km de calles',
    'boot.fail': 'Los archivos de datos no cargaron.',

    'pc.k': 'Tarjeta para caminar / Safe Routes to School',
    'pc.to': 'a {school}',
    'pc.from': 'Desde {from}',
    'pc.when': 'Para la {win} ({clock}), {mode}.',
    'pc.mode.foot': 'a pie', 'pc.mode.bus': 'en autobús o tren',
    'pc.opt': 'Opción', 'pc.time': 'Tiempo', 'pc.walk': 'A pie', 'pc.exp': 'Exposición',
    'pc.turns': 'Calle por calle', 'pc.hours': 'Misma ruta, otra hora',
    'pc.open': 'Abre este viaje en un teléfono',
    'pc.foot': 'Las puntuaciones van de 0 a 100 frente a todas las cuadras de Los Ángeles a esa hora; menos es más tranquilo. Es una segunda opinión sobre una caminata, no una garantía. Datos: LAPD 2020 a 2024, LA Metro, OpenStreetMap.',
    'pc.printed': 'Impreso el {date}',
  },
};

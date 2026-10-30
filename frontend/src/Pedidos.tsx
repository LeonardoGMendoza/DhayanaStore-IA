import { useCallback, useEffect, useState } from 'react'
import { API, api, leerToken, mensajeDeError } from './api'

type Item = { nombre: string; cantidad: number; precio: number; costo: number }
type Pedido = {
  id: number
  codigo: string
  creado_en: string
  cliente_nombre: string
  cliente_telefono: string
  direccion: string
  distrito: string
  items: Item[]
  total_productos: number
  costo_productos: number
  ganancia: number
  delivery: number
  total_cliente: number
  motorizado: string
  estado: string
  pago: string
  metodo_pago: string
  siguiente: string | null
  mensaje: string
  whatsapp: string
}
type Resumen = {
  pedidos: number
  entregados: number
  rechazados: number
  en_curso: number
  ventas: number
  ganancia: number
  ventas_previstas: number
  por_repasar: number
}

const NOMBRE_ESTADO: Record<string, string> = {
  nuevo: 'Nuevo',
  confirmado: 'Confirmado',
  recogido: 'Recogido',
  en_camino: 'En camino',
  entregado: 'Entregado',
  rechazado: 'Rechazado',
  cancelado: 'Cancelado',
}
const BOTON_SIGUIENTE: Record<string, string> = {
  confirmado: 'Confirmar',
  recogido: 'Ya lo recogió',
  en_camino: 'Salió 🛵',
  entregado: 'Entregado ✓',
}
const FINALES = ['entregado', 'rechazado', 'cancelado']
const S = (n: number) => `S/ ${Number(n.toFixed(2))}`
const vacio = (): Item => ({ nombre: '', cantidad: 1, precio: 0, costo: 0 })

function Formulario({ alGuardar, alCerrar }: { alGuardar: () => void; alCerrar: () => void }) {
  const [mensaje, setMensaje] = useState('')
  const [nombre, setNombre] = useState('')
  const [telefono, setTelefono] = useState('')
  const [distrito, setDistrito] = useState('')
  const [direccion, setDireccion] = useState('')
  const [delivery, setDelivery] = useState('')
  const [motorizado, setMotorizado] = useState('')
  const [origen, setOrigen] = useState('catalogo')
  const [items, setItems] = useState<Item[]>([vacio()])
  const [error, setError] = useState('')
  const [ocupado, setOcupado] = useState(false)

  const total = items.reduce((s, i) => s + i.cantidad * i.precio, 0)
  const costo = items.reduce((s, i) => s + i.cantidad * i.costo, 0)

  function cambiar(idx: number, campo: keyof Item, valor: string) {
    setItems((xs) => xs.map((x, i) => (i === idx ? { ...x, [campo]: campo === 'nombre' ? valor : Number(valor) || 0 } : x)))
  }

  async function leerMensaje() {
    setError('')
    try {
      const d = await api<{ cliente_nombre: string; direccion: string; items: Item[] }>('/pedidos/leer-mensaje', {
        method: 'POST',
        body: JSON.stringify({ texto: mensaje }),
      })
      if (d.cliente_nombre) setNombre(d.cliente_nombre)
      if (d.direccion) setDireccion(d.direccion)
      if (d.items.length) setItems(d.items)
      else setError('No encontré productos en ese mensaje. Llénalos a mano.')
    } catch (e) {
      setError(mensajeDeError(e))
    }
  }

  async function guardar() {
    setOcupado(true)
    setError('')
    try {
      await api('/pedidos', {
        method: 'POST',
        body: JSON.stringify({
          cliente_nombre: nombre,
          cliente_telefono: telefono,
          distrito,
          direccion,
          delivery: Number(delivery) || 0,
          motorizado,
          origen,
          items: items.filter((i) => i.nombre.trim()),
        }),
      })
      alGuardar()
    } catch (e) {
      setError(mensajeDeError(e))
    } finally {
      setOcupado(false)
    }
  }

  return (
    <section className="card">
      <div className="head">
        <h2>Nuevo pedido</h2>
        <button className="btn-copy" onClick={alCerrar}>Cerrar</button>
      </div>

      <label htmlFor="msg">¿Llegó por el catálogo? Pega aquí el mensaje de WhatsApp (opcional)</label>
      <textarea id="msg" rows={4} value={mensaje} onChange={(e) => setMensaje(e.target.value)} placeholder="Ej.: ¡Hola! Vi su catálogo y quiero pedir: • 1 × Zapatero de madera — S/ 85 …" />
      <button className="btn-sec" disabled={mensaje.trim().length < 5} onClick={leerMensaje}>Leer mensaje</button>

      <div className="row">
        <div><label htmlFor="nom">Cliente</label><input id="nom" value={nombre} onChange={(e) => setNombre(e.target.value)} /></div>
        <div><label htmlFor="tel">WhatsApp del cliente</label><input id="tel" inputMode="tel" value={telefono} onChange={(e) => setTelefono(e.target.value)} placeholder="Ej.: 987654321" /></div>
        <div><label htmlFor="dis">Distrito</label><input id="dis" value={distrito} onChange={(e) => setDistrito(e.target.value)} placeholder="Ej.: La Esperanza" /></div>
        <div><label htmlFor="del">Delivery (S/)</label><input id="del" inputMode="decimal" value={delivery} onChange={(e) => setDelivery(e.target.value)} placeholder="Ej.: 7" /></div>
      </div>
      <label htmlFor="dir" className="mt">Dirección</label>
      <input id="dir" value={direccion} onChange={(e) => setDireccion(e.target.value)} />
      <div className="row">
        <div><label htmlFor="mot">Motorizado</label><input id="mot" value={motorizado} onChange={(e) => setMotorizado(e.target.value)} /></div>
        <div>
          <label htmlFor="ori">¿De dónde vino?</label>
          <select id="ori" value={origen} onChange={(e) => setOrigen(e.target.value)}>
            <option value="catalogo">Catálogo web</option>
            <option value="marketplace">Marketplace</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="otro">Otro</option>
          </select>
        </div>
      </div>

      <h3>Productos</h3>
      <div className="items">
        <div className="items-head"><span>Producto</span><span>Cant.</span><span>Precio c/u</span><span>Costo c/u</span><span /></div>
        {items.map((it, i) => (
          <div className="items-row" key={i}>
            <input aria-label="Producto" value={it.nombre} onChange={(e) => cambiar(i, 'nombre', e.target.value)} />
            <input aria-label="Cantidad" inputMode="numeric" value={it.cantidad} onChange={(e) => cambiar(i, 'cantidad', e.target.value)} />
            <input aria-label="Precio" inputMode="decimal" value={it.precio} onChange={(e) => cambiar(i, 'precio', e.target.value)} />
            <input aria-label="Costo" inputMode="decimal" value={it.costo} onChange={(e) => cambiar(i, 'costo', e.target.value)} />
            <button className="btn-x" aria-label="Quitar" onClick={() => setItems((xs) => (xs.length > 1 ? xs.filter((_, j) => j !== i) : [vacio()]))}>×</button>
          </div>
        ))}
      </div>
      <button className="btn-sec" onClick={() => setItems((xs) => [...xs, vacio()])}>+ Agregar producto</button>

      <p className="totales">
        Productos <b>{S(total)}</b> · Delivery <b>{S(Number(delivery) || 0)}</b> · El cliente paga <b>{S(total + (Number(delivery) || 0))}</b> · Ganas <b className="verde">{S(total - costo)}</b>
      </p>
      <button className="btn-main" disabled={ocupado || !nombre.trim() || !items.some((i) => i.nombre.trim())} onClick={guardar}>
        {ocupado ? 'Guardando…' : 'Guardar pedido'}
      </button>
      {error && <p className="error">{error}</p>}
    </section>
  )
}

function Tarjeta({ p, alCambiar }: { p: Pedido; alCambiar: () => void }) {
  const [error, setError] = useState('')
  const final = FINALES.includes(p.estado)

  async function estado(nuevo: string) {
    setError('')
    try {
      await api(`/pedidos/${p.id}/estado`, { method: 'POST', body: JSON.stringify({ estado: nuevo }) })
      alCambiar()
    } catch (e) {
      setError(mensajeDeError(e))
    }
  }
  async function cambiar(campos: Record<string, string>) {
    setError('')
    try {
      await api(`/pedidos/${p.id}`, { method: 'PATCH', body: JSON.stringify(campos) })
      alCambiar()
    } catch (e) {
      setError(mensajeDeError(e))
    }
  }

  return (
    <article className={`card pedido est-${p.estado}`}>
      <div className="head">
        <div>
          <b>{p.cliente_nombre}</b> <span className="cod">#{p.codigo}</span>
          <div className="hint">{[p.distrito, p.direccion].filter(Boolean).join(' · ') || 'Sin dirección'} · {p.creado_en.slice(11, 16)}</div>
        </div>
        <span className={`chip est-${p.estado}`}>{NOMBRE_ESTADO[p.estado]}</span>
      </div>
      <ul className="lista">
        {p.items.map((i, k) => <li key={k}>{i.cantidad} × {i.nombre} <span>{S(i.cantidad * i.precio)}</span></li>)}
      </ul>
      <p className="totales">
        Cobrar <b>{S(p.total_cliente)}</b> (delivery {S(p.delivery)}) · Ganas <b className="verde">{S(p.ganancia)}</b>
        {p.motorizado && <> · 🛵 {p.motorizado}</>}
      </p>

      <div className="acciones">
        {p.siguiente && <button className="btn-main chico" onClick={() => estado(p.siguiente!)}>{BOTON_SIGUIENTE[p.siguiente]}</button>}
        {p.whatsapp && <a className="btn-wa" href={p.whatsapp} target="_blank" rel="noreferrer">📲 Avisar al cliente</a>}
        {!final && <button className="btn-sec" onClick={() => estado('rechazado')} title="El cliente no recibió el pedido">No lo recibió</button>}
        {!final && <button className="btn-link" onClick={() => estado('cancelado')}>Cancelar</button>}
      </div>
      <div className="pago">
        <label>Pago
          <select value={p.pago} onChange={(e) => cambiar({ pago: e.target.value })}>
            <option value="pendiente">Pendiente</option>
            <option value="pagado">Motorizado cobró</option>
            <option value="repasado">Me pasó el dinero ✓</option>
          </select>
        </label>
        <label>Medio
          <select value={p.metodo_pago} onChange={(e) => cambiar({ metodo_pago: e.target.value })}>
            <option value="">—</option>
            <option value="yape">Yape</option>
            <option value="plin">Plin</option>
            <option value="efectivo">Efectivo</option>
            <option value="transferencia">Transferencia</option>
          </select>
        </label>
      </div>
      {!p.cliente_telefono && !final && <p className="hint">Agrega el WhatsApp del cliente para avisarle con un toque.</p>}
      {error && <p className="error">{error}</p>}
    </article>
  )
}

export default function Pedidos() {
  const [lista, setLista] = useState<Pedido[]>([])
  const [resumen, setResumen] = useState<Resumen | null>(null)
  const [todos, setTodos] = useState(false)
  const [nuevo, setNuevo] = useState(false)
  const [error, setError] = useState('')

  const cargar = useCallback(async () => {
    try {
      const [l, r] = await Promise.all([
        api<Pedido[]>(`/pedidos${todos ? '?todos=true' : ''}`),
        api<Resumen>('/pedidos/resumen'),
      ])
      setLista(l)
      setResumen(r)
      setError('')
    } catch (e) {
      setError(mensajeDeError(e))
    }
  }, [todos])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function descargarDataset() {
    try {
      const r = await fetch(`${API}/pedidos/dataset.csv`, { headers: { 'X-Admin-Token': leerToken() } })
      if (!r.ok) throw new Error('No pude descargar el dataset.')
      const url = URL.createObjectURL(await r.blob())
      const a = document.createElement('a')
      a.href = url
      a.download = 'pedidos_dataset.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(mensajeDeError(e))
    }
  }

  return (
    <>
      {resumen && (
        <section className="card resumen cinco">
          <div><span>Pedidos hoy</span><b>{resumen.pedidos}</b></div>
          <div><span>Entregados</span><b>{resumen.entregados}</b></div>
          <div><span>Vendido</span><b>{S(resumen.ventas)}</b></div>
          <div><span>Ganancia</span><b className="verde">{S(resumen.ganancia)}</b></div>
          <div><span>Motorizado debe</span><b className={resumen.por_repasar ? 'rojo' : ''}>{S(resumen.por_repasar)}</b></div>
        </section>
      )}

      {nuevo ? (
        <Formulario alCerrar={() => setNuevo(false)} alGuardar={() => { setNuevo(false); cargar() }} />
      ) : (
        <button className="btn-main" onClick={() => setNuevo(true)}>+ Nuevo pedido</button>
      )}

      <div className="barra">
        <label className="check"><input type="checkbox" checked={todos} onChange={(e) => setTodos(e.target.checked)} /> Ver todos los días</label>
        <button className="btn-link" onClick={cargar}>↻ Actualizar</button>
        <button className="btn-link" onClick={descargarDataset}>⬇ Dataset (CSV)</button>
      </div>

      {error && <p className="error">{error}</p>}
      {!error && lista.length === 0 && <p className="vacio">Todavía no hay pedidos {todos ? '' : 'hoy'}.</p>}
      {lista.map((p) => <Tarjeta key={p.id} p={p} alCambiar={cargar} />)}
    </>
  )
}

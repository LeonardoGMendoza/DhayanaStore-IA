import { useState } from 'react'

const API = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

type Anuncio = {
  id: string
  titulo: string
  nombre: string
  descripcion: string
  descripcion_corta: string
  categoria: string
  precio: number
  costo: number
  ganancia: number
  anuncio: string
}

function bloqueCatalogo(a: Anuncio): string {
  const s = (t: string) => JSON.stringify(t)
  return `  {
    id: ${s(a.id)},
    nombre: ${s(a.nombre)},
    categoria: ${s(a.categoria)},
    precio: ${a.precio},
    costo: ${a.costo},
    foto: "",
    disponible: true,
    descripcion: ${s(a.descripcion_corta)},
  },`
}

function Copiar({ texto }: { texto: string }) {
  const [ok, setOk] = useState(false)
  return (
    <button
      className="btn-copy"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(texto)
          setOk(true)
          setTimeout(() => setOk(false), 1500)
        } catch {
          /* sin permiso de portapapeles: el texto se puede seleccionar a mano */
        }
      }}
    >
      {ok ? '✓ Copiado' : 'Copiar'}
    </button>
  )
}

export default function App() {
  const [texto, setTexto] = useState('')
  const [costo, setCosto] = useState('')
  const [ganancia, setGanancia] = useState('20')
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [res, setRes] = useState<Anuncio | null>(null)
  const [anuncio, setAnuncio] = useState('')

  async function generar() {
    setCargando(true)
    setError('')
    try {
      const r = await fetch(`${API}/redator`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texto, costo: Number(costo) || 0, ganancia: Number(ganancia) || 0 }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail ?? 'Error')
      setRes(d)
      setAnuncio(d.anuncio)
    } catch (e) {
      setError(e instanceof Error && e.message !== 'Failed to fetch' ? e.message : 'No pude conectar con el servidor.')
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Dhayana Store</h1>
        <p>✍️ Redactor de anuncios con IA</p>
      </header>

      <main>
        <section className="card">
          <label htmlFor="texto">1. Pega el texto del proveedor (del grupo de WhatsApp)</label>
          <textarea
            id="texto"
            rows={8}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder={'MESA AUXILIAR CON DIVISIONES\n⚡ Altura ajustable\n⚡ 4 ruedas giratorias\n⚡ PRECIO: 70 SOLES'}
          />
          <div className="row">
            <div>
              <label htmlFor="costo">2. ¿Cuánto te cuesta? (S/)</label>
              <input id="costo" inputMode="decimal" value={costo} onChange={(e) => setCosto(e.target.value)} placeholder="70" />
            </div>
            <div>
              <label htmlFor="ganancia">¿Cuánto quieres ganar? (S/)</label>
              <input id="ganancia" inputMode="decimal" value={ganancia} onChange={(e) => setGanancia(e.target.value)} />
            </div>
          </div>
          <button className="btn-main" disabled={cargando || texto.trim().length < 5} onClick={generar}>
            {cargando ? 'Escribiendo…' : 'Crear anuncio'}
          </button>
          {error && <p className="error">{error}</p>}
        </section>

        {res && (
          <>
            <section className="card resumen">
              <div><span>Precio de venta</span><b>{res.precio ? `S/ ${res.precio}` : '—'}</b></div>
              <div><span>Ganas</span><b className="verde">{res.ganancia ? `S/ ${res.ganancia}` : '—'}</b></div>
              <div><span>Categoría</span><b>{res.categoria}</b></div>
            </section>

            <section className="card">
              <div className="head">
                <h2>Anuncio para Marketplace</h2>
                <Copiar texto={anuncio} />
              </div>
              <p className="hint">Revísalo y corrige lo que quieras antes de publicar.</p>
              <textarea rows={12} value={anuncio} onChange={(e) => setAnuncio(e.target.value)} />
            </section>

            <section className="card">
              <div className="head">
                <h2>Para el catálogo web</h2>
                <Copiar texto={bloqueCatalogo(res)} />
              </div>
              <p className="hint">
                Pega este bloque al final de <code>productos.js</code> (antes del <code>];</code>). Foto:{' '}
                <code>img/{res.id}.jpg</code>
              </p>
              <pre>{bloqueCatalogo(res)}</pre>
            </section>
          </>
        )}
      </main>
    </div>
  )
}

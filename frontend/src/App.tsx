import { useState } from 'react'
import { guardarToken, leerToken } from './api'
import Pedidos from './Pedidos'
import Redactor from './Redactor'

type Pestana = 'pedidos' | 'redactor'

export default function App() {
  const [pestana, setPestana] = useState<Pestana>('pedidos')
  const [token, setToken] = useState(leerToken())
  const [verClave, setVerClave] = useState(false)

  return (
    <div className="app">
      <header>
        <div className="top">
          <h1>Dhayana Store</h1>
          <button className="btn-clave" onClick={() => setVerClave((v) => !v)} aria-label="Clave del panel">🔑</button>
        </div>
        {verClave && (
          <div className="clave">
            <input
              type="password"
              placeholder="Clave del panel"
              value={token}
              onChange={(e) => { setToken(e.target.value); guardarToken(e.target.value) }}
            />
          </div>
        )}
        <nav>
          <button className={pestana === 'pedidos' ? 'activo' : ''} onClick={() => setPestana('pedidos')}>📦 Pedidos</button>
          <button className={pestana === 'redactor' ? 'activo' : ''} onClick={() => setPestana('redactor')}>✍️ Redactor de anuncios</button>
        </nav>
      </header>
      <main>{pestana === 'pedidos' ? <Pedidos /> : <Redactor />}</main>
    </div>
  )
}

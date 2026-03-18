import { useIdeas } from './hooks/useIdeas'

function App() {
  const { ideas, stats, loading, error } = useIdeas()
  if (loading) return <div>Loading...</div>
  if (error) return <div>Error: {error}</div>
  return <div>{stats?.total} ideas loaded. First: {ideas[0]?.name}</div>
}

export default App

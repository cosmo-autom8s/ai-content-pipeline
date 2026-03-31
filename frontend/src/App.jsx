import styled, { keyframes } from 'styled-components'
import { useIdeas } from './hooks/useIdeas'
import Layout from './components/Layout'
import FilterBar from './components/FilterBar'
import IdeaCard from './components/IdeaCard'
import IdeaDetail from './components/IdeaDetail'

const CardGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: ${({ theme }) => theme.spacing.lg};
`

const spin = keyframes`
  to { transform: rotate(360deg); }
`

const SpinnerWrapper = styled.div`
  display: flex;
  justify-content: center;
  padding: ${({ theme }) => theme.spacing.xxl};
`

const SpinnerCircle = styled.div`
  width: 32px;
  height: 32px;
  border: 3px solid ${({ theme }) => theme.colors.border};
  border-top-color: ${({ theme }) => theme.colors.accent};
  border-radius: 50%;
  animation: ${spin} 0.8s linear infinite;
`

function Spinner() {
  return (
    <SpinnerWrapper>
      <SpinnerCircle />
    </SpinnerWrapper>
  )
}

const ErrorBannerWrapper = styled.div`
  background: rgba(248, 113, 113, 0.1);
  border: 1px solid ${({ theme }) => theme.colors.score.low};
  border-radius: ${({ theme }) => theme.radius.md};
  padding: ${({ theme }) => theme.spacing.md};
  margin-bottom: ${({ theme }) => theme.spacing.lg};
  color: ${({ theme }) => theme.colors.score.low};
  font-size: ${({ theme }) => theme.fontSize.sm};
`

function ErrorBanner({ message }) {
  return <ErrorBannerWrapper>Error: {message}</ErrorBannerWrapper>
}

const EmptyWrapper = styled.div`
  text-align: center;
  padding: ${({ theme }) => theme.spacing.xxl};
  color: ${({ theme }) => theme.colors.textMuted};
  font-size: ${({ theme }) => theme.fontSize.md};
`

function EmptyState() {
  return <EmptyWrapper>No ideas match your filters</EmptyWrapper>
}

function App() {
  const { ideas, stats, loading, error, filters, updateFilters, selectIdea, selectedIdea, closeDetail } = useIdeas()

  return (
    <>
      <Layout stats={stats}>
        <FilterBar filters={filters} onFilterChange={updateFilters} ideas={ideas} />
        {loading && <Spinner />}
        {error && <ErrorBanner message={error} />}
        <CardGrid>
          {ideas.map((idea) => (
            <IdeaCard key={idea.id} idea={idea} onClick={() => selectIdea(idea.id)} />
          ))}
        </CardGrid>
        {ideas.length === 0 && !loading && <EmptyState />}
      </Layout>
      {selectedIdea && (
        <IdeaDetail idea={selectedIdea} onClose={closeDetail} />
      )}
    </>
  )
}

export default App

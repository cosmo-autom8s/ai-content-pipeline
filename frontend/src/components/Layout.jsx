import styled from 'styled-components'

const Wrapper = styled.div`
  min-height: 100vh;
  background: ${({ theme }) => theme.colors.bg};
  color: ${({ theme }) => theme.colors.text};
  font-family: ${({ theme }) => theme.fonts.body};
`

const Header = styled.header`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.xl};
  background: ${({ theme }) => theme.colors.surface};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  box-shadow: ${({ theme }) => theme.shadows.card};
`

const AppName = styled.h1`
  margin: 0;
  font-size: ${({ theme }) => theme.fontSize.lg};
  font-weight: 700;
  color: ${({ theme }) => theme.colors.text};
`

const StatsSummary = styled.span`
  font-size: ${({ theme }) => theme.fontSize.sm};
  color: ${({ theme }) => theme.colors.textMuted};
`

const Main = styled.main`
  padding: ${({ theme }) => theme.spacing.xl};
  padding-top: calc(60px + ${({ theme }) => theme.spacing.xl});
  max-width: 1440px;
  margin: 0 auto;
`

function Layout({ stats, children }) {
  const summaryText = stats
    ? `${stats.total} ideas, ${stats.top_picks} top picks`
    : ''

  return (
    <Wrapper>
      <Header>
        <AppName>Content Ideas</AppName>
        {stats && <StatsSummary>{summaryText}</StatsSummary>}
      </Header>
      <Main>{children}</Main>
    </Wrapper>
  )
}

export default Layout

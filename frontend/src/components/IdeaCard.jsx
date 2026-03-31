import styled, { useTheme } from 'styled-components'

const Card = styled.div`
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.md};
  box-shadow: ${({ theme }) => theme.shadows.card};
  padding: ${({ theme }) => theme.spacing.lg};
  cursor: pointer;
  transition: background 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.sm};
  min-width: 0;
  overflow: hidden;

  &:hover {
    background: ${({ theme }) => theme.colors.surfaceHover};
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  }
`

const TopRow = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing.sm};
`

const Score = styled.span`
  font-size: ${({ theme }) => theme.fontSize.xl};
  font-weight: 800;
  font-family: ${({ theme }) => theme.fonts.mono};
  line-height: 1;
  color: ${({ $color }) => $color};
`

const BadgeRow = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.xs};
  flex-wrap: wrap;
`

const TopPickBadge = styled.span`
  display: inline-block;
  font-size: ${({ theme }) => theme.fontSize.xs};
  font-weight: 700;
  color: ${({ theme }) => theme.colors.score.high};
  background: rgba(74, 222, 128, 0.12);
  padding: 2px ${({ theme }) => theme.spacing.xs};
  border-radius: ${({ theme }) => theme.radius.sm};
  text-transform: uppercase;
  letter-spacing: 0.5px;
`

const Name = styled.h3`
  margin: 0;
  font-size: ${({ theme }) => theme.fontSize.md};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.text};
  line-height: 1.4;
`

const Label = styled.span`
  font-size: ${({ theme }) => theme.fontSize.xs};
  color: ${({ theme }) => theme.colors.textMuted};
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`

const Pill = styled.span`
  display: inline-block;
  font-size: ${({ theme }) => theme.fontSize.xs};
  font-weight: 600;
  padding: 2px ${({ theme }) => theme.spacing.sm};
  border-radius: 999px;
  background: ${({ $bg }) => $bg}22;
  color: ${({ $bg }) => $bg};
  white-space: nowrap;
`

const TagRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.spacing.xs};
`

const SmallTag = styled.span`
  display: inline-block;
  font-size: 11px;
  padding: 1px ${({ theme }) => theme.spacing.xs};
  border-radius: ${({ theme }) => theme.radius.sm};
  background: ${({ theme }) => theme.colors.border};
  color: ${({ theme }) => theme.colors.textMuted};
`

const MetaRow = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
  margin-top: auto;
  flex-wrap: wrap;
`

const PriorityDot = styled.span`
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: ${({ $color }) => $color};
  flex-shrink: 0;
`

function getScoreColor(score, theme) {
  if (score === null || score === undefined) return theme.colors.textMuted
  if (score >= 8) return theme.colors.score.high
  if (score >= 6) return theme.colors.score.mid
  return theme.colors.score.low
}

function formatStatus(status) {
  if (!status) return ''
  return status.replace(/_/g, ' ')
}

function IdeaCard({ idea, onClick }) {
  const theme = useTheme()
  const scoreColor = getScoreColor(idea.score, theme)
  const statusColor = theme.colors.status[idea.status] || theme.colors.textMuted
  const priorityColor = idea.filming_priority
    ? theme.colors.filmingPriority[idea.filming_priority] || theme.colors.textMuted
    : null

  return (
    <Card onClick={onClick}>
      <TopRow>
        <Score $color={scoreColor}>
          {idea.score !== null && idea.score !== undefined ? idea.score : '\u2013'}
        </Score>
        <BadgeRow>
          {idea.top_pick && <TopPickBadge>Top Pick</TopPickBadge>}
          {priorityColor && (
            <PriorityDot $color={priorityColor} title={formatStatus(idea.filming_priority)} />
          )}
        </BadgeRow>
      </TopRow>

      <Name title={idea.name}>{idea.name}</Name>

      {idea.description && <Label>{idea.description}</Label>}

      <MetaRow>
        {idea.format && (
          <Pill $bg={theme.colors.accent}>{idea.format}</Pill>
        )}
        <Pill $bg={statusColor}>{formatStatus(idea.status)}</Pill>
      </MetaRow>

      {idea.filming_setup && idea.filming_setup.length > 0 && (
        <TagRow>
          {idea.filming_setup.map((setup) => (
            <SmallTag key={setup}>{setup}</SmallTag>
          ))}
        </TagRow>
      )}
    </Card>
  )
}

export default IdeaCard

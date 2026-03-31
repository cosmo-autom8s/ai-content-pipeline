import { useEffect } from 'react'
import styled, { keyframes, useTheme } from 'styled-components'

const fadeIn = keyframes`
  from { opacity: 0; }
  to { opacity: 1; }
`

const slideIn = keyframes`
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
`

const Overlay = styled.div`
  position: fixed;
  inset: 0;
  background: ${({ theme }) => theme.colors.overlay};
  z-index: 900;
  animation: ${fadeIn} 0.3s ease;
`

const Panel = styled.aside`
  position: fixed;
  top: 0;
  right: 0;
  width: 45%;
  height: 100vh;
  background: ${({ theme }) => theme.colors.surface};
  box-shadow: ${({ theme }) => theme.shadows.panel};
  z-index: 1000;
  overflow-y: auto;
  animation: ${slideIn} 0.3s ease;
  display: flex;
  flex-direction: column;

  @media (max-width: 900px) {
    width: 85%;
  }
`

const PanelContent = styled.div`
  padding: ${({ theme }) => theme.spacing.xl};
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.lg};
`

const CloseButton = styled.button`
  position: sticky;
  top: 0;
  align-self: flex-end;
  background: ${({ theme }) => theme.colors.bg};
  border: 1px solid ${({ theme }) => theme.colors.border};
  color: ${({ theme }) => theme.colors.textMuted};
  font-size: ${({ theme }) => theme.fontSize.lg};
  width: 36px;
  height: 36px;
  border-radius: ${({ theme }) => theme.radius.sm};
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: ${({ theme }) => theme.spacing.md};
  margin-bottom: 0;
  flex-shrink: 0;
  z-index: 1;
  transition: color 0.15s ease, border-color 0.15s ease;

  &:hover {
    color: ${({ theme }) => theme.colors.text};
    border-color: ${({ theme }) => theme.colors.textMuted};
  }
`

const Section = styled.section`
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  padding-bottom: ${({ theme }) => theme.spacing.lg};

  &:last-child {
    border-bottom: none;
  }
`

const SectionTitle = styled.h4`
  margin: 0 0 ${({ theme }) => theme.spacing.sm} 0;
  font-size: ${({ theme }) => theme.fontSize.sm};
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: ${({ theme }) => theme.colors.textMuted};
`

// --- Header ---

const HeaderRow = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing.md};
`

const HeaderLeft = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.sm};
  min-width: 0;
`

const IdeaName = styled.h2`
  margin: 0;
  font-size: ${({ theme }) => theme.fontSize.lg};
  font-weight: 700;
  color: ${({ theme }) => theme.colors.text};
  line-height: 1.3;
`

const BadgeRow = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.xs};
  flex-wrap: wrap;
`

const BigScore = styled.span`
  font-size: ${({ theme }) => theme.fontSize.md};
  font-weight: 800;
  font-family: ${({ theme }) => theme.fonts.mono};
  line-height: 1;
  color: ${({ $color }) => $color};
  flex-shrink: 0;
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

// --- Hooks ---

const HookList = styled.ol`
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.md};
`

const HookItem = styled.li`
  display: flex;
  gap: ${({ theme }) => theme.spacing.sm};
  align-items: baseline;
`

const HookNumber = styled.span`
  font-size: ${({ theme }) => theme.fontSize.lg};
  font-weight: 800;
  font-family: ${({ theme }) => theme.fonts.mono};
  color: ${({ theme }) => theme.colors.accent};
  flex-shrink: 0;
  min-width: 28px;
`

const HookText = styled.span`
  font-size: ${({ theme }) => theme.fontSize.md};
  color: ${({ theme }) => theme.colors.text};
  line-height: 1.5;
`

// --- Overview rows ---

const LabeledRow = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing.sm};
  padding: ${({ theme }) => theme.spacing.xs} 0;

  & + & {
    border-top: 1px solid ${({ theme }) => theme.colors.border}44;
  }
`

const RowLabel = styled.span`
  font-size: ${({ theme }) => theme.fontSize.sm};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.textMuted};
  min-width: 110px;
  flex-shrink: 0;
`

const RowValue = styled.span`
  font-size: ${({ theme }) => theme.fontSize.sm};
  color: ${({ theme }) => theme.colors.text};
  line-height: 1.5;
`

// --- Reasoning ---

const ReasoningBlock = styled.div`
  font-family: ${({ theme }) => theme.fonts.mono};
  font-size: ${({ theme }) => theme.fontSize.sm};
  color: ${({ theme }) => theme.colors.textMuted};
  line-height: 1.7;
  font-style: italic;
  white-space: pre-wrap;
`

// --- Tag pills ---

const TagRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.spacing.xs};
`

const SmallTag = styled.span`
  display: inline-block;
  font-size: 11px;
  padding: 2px ${({ theme }) => theme.spacing.sm};
  border-radius: ${({ theme }) => theme.radius.sm};
  background: ${({ theme }) => theme.colors.border};
  color: ${({ theme }) => theme.colors.textMuted};
`

// --- Caption blocks ---

const CaptionBlock = styled.div`
  background: ${({ theme }) => theme.colors.bg};
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: ${({ theme }) => theme.spacing.md};

  & + & {
    margin-top: ${({ theme }) => theme.spacing.sm};
  }
`

const CaptionLabel = styled.div`
  font-size: ${({ theme }) => theme.fontSize.xs};
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: ${({ theme }) => theme.colors.textMuted};
  margin-bottom: ${({ theme }) => theme.spacing.xs};
`

const CaptionText = styled.div`
  font-family: ${({ theme }) => theme.fonts.mono};
  font-size: ${({ theme }) => theme.fontSize.sm};
  color: ${({ theme }) => theme.colors.text};
  line-height: 1.6;
  white-space: pre-wrap;
`

// --- Links ---

const StyledLink = styled.a`
  color: ${({ theme }) => theme.colors.accent};
  text-decoration: none;
  word-break: break-all;

  &:hover {
    text-decoration: underline;
  }
`

// --- Helpers ---

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

function formatDate(iso) {
  if (!iso) return null
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return iso
  }
}

// --- Component ---

function IdeaDetail({ idea, onClose }) {
  const theme = useTheme()

  // Close on Escape key
  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  // Prevent body scroll while panel is open
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = ''
    }
  }, [])

  if (!idea) return null

  const scoreColor = getScoreColor(idea.score, theme)
  const statusColor = theme.colors.status[idea.status] || theme.colors.textMuted
  const priorityColor = idea.filming_priority
    ? theme.colors.filmingPriority[idea.filming_priority] || theme.colors.textMuted
    : null

  // Collect hooks
  const hooks = [idea.hook_1, idea.hook_2, idea.hook_3, idea.hook_4, idea.hook_5].filter(
    (h) => h && h.trim()
  )

  // Captions
  const captions = [
    { label: 'TikTok', value: idea.caption_tiktok },
    { label: 'Instagram', value: idea.caption_instagram },
    { label: 'YouTube', value: idea.caption_youtube },
    { label: 'LinkedIn', value: idea.caption_linkedin },
  ].filter((c) => c.value)

  const hasCaptions = captions.length > 0

  // Dates
  const hasDates =
    idea.filmed_date || idea.posted_date || (idea.post_urls && Object.keys(idea.post_urls).length > 0)

  // Post URLs
  const postUrlEntries = idea.post_urls
    ? Object.entries(idea.post_urls).filter(([, url]) => url)
    : []

  return (
    <>
      <Overlay onClick={onClose} />
      <Panel>
        <CloseButton onClick={onClose} aria-label="Close detail panel">
          &times;
        </CloseButton>
        <PanelContent>
          {/* 1. Header */}
          <Section>
            <HeaderRow>
              <HeaderLeft>
                <IdeaName>{idea.name}</IdeaName>
                <BadgeRow>
                  {idea.top_pick && <TopPickBadge>Top Pick</TopPickBadge>}
                  <Pill $bg={statusColor}>{formatStatus(idea.status)}</Pill>
                  {idea.format && <Pill $bg={theme.colors.accent}>{idea.format}</Pill>}
                </BadgeRow>
              </HeaderLeft>
              <BigScore $color={scoreColor}>
                {idea.score !== null && idea.score !== undefined ? idea.score : '\u2013'}
              </BigScore>
            </HeaderRow>
          </Section>

          {/* 2. Hooks */}
          {hooks.length > 0 && (
            <Section>
              <SectionTitle>Hooks</SectionTitle>
              <HookList>
                {hooks.map((hook, i) => (
                  <HookItem key={i}>
                    <HookNumber>{i + 1}.</HookNumber>
                    <HookText>{hook}</HookText>
                  </HookItem>
                ))}
              </HookList>
            </Section>
          )}

          {/* 3. Overview */}
          <Section>
            <SectionTitle>Overview</SectionTitle>
            {idea.description && (
              <LabeledRow>
                <RowLabel>Description</RowLabel>
                <RowValue>{idea.description}</RowValue>
              </LabeledRow>
            )}
            {idea.angle && (
              <LabeledRow>
                <RowLabel>Angle</RowLabel>
                <RowValue>{idea.angle}</RowValue>
              </LabeledRow>
            )}
            {idea.main_topic && (
              <LabeledRow>
                <RowLabel>Main Topic</RowLabel>
                <RowValue>{idea.main_topic}</RowValue>
              </LabeledRow>
            )}
            {idea.format && (
              <LabeledRow>
                <RowLabel>Format</RowLabel>
                <RowValue>{idea.format}</RowValue>
              </LabeledRow>
            )}
            {idea.urgency && (
              <LabeledRow>
                <RowLabel>Urgency</RowLabel>
                <RowValue>{idea.urgency}</RowValue>
              </LabeledRow>
            )}
          </Section>

          {/* 4. Reasoning */}
          {idea.reasoning && (
            <Section>
              <SectionTitle>Reasoning</SectionTitle>
              <ReasoningBlock>{idea.reasoning}</ReasoningBlock>
            </Section>
          )}

          {/* 5. Filming */}
          {(idea.filming_setup?.length > 0 || priorityColor || idea.frame_type?.length > 0) && (
            <Section>
              <SectionTitle>Filming</SectionTitle>
              {idea.filming_setup && idea.filming_setup.length > 0 && (
                <TagRow style={{ marginBottom: '8px' }}>
                  {idea.filming_setup.map((setup) => (
                    <Pill key={setup} $bg={theme.colors.accent}>
                      {setup}
                    </Pill>
                  ))}
                </TagRow>
              )}
              {idea.filming_priority && (
                <TagRow style={{ marginBottom: '8px' }}>
                  <Pill $bg={priorityColor || theme.colors.textMuted}>
                    {formatStatus(idea.filming_priority)}
                  </Pill>
                </TagRow>
              )}
              {idea.frame_type && idea.frame_type.length > 0 && (
                <TagRow>
                  {idea.frame_type.map((ft) => (
                    <SmallTag key={ft}>{ft}</SmallTag>
                  ))}
                </TagRow>
              )}
            </Section>
          )}

          {/* 6. Meta */}
          <Section>
            <SectionTitle>Meta</SectionTitle>
            {idea.topic_cluster && (
              <LabeledRow>
                <RowLabel>Topic Cluster</RowLabel>
                <RowValue>{idea.topic_cluster}</RowValue>
              </LabeledRow>
            )}
            {idea.original_url && (
              <LabeledRow>
                <RowLabel>Original URL</RowLabel>
                <RowValue>
                  <StyledLink href={idea.original_url} target="_blank" rel="noopener noreferrer">
                    {idea.original_url}
                  </StyledLink>
                </RowValue>
              </LabeledRow>
            )}
            {idea.source_link && (
              <LabeledRow>
                <RowLabel>Source</RowLabel>
                <RowValue>
                  {idea.source_link.name}
                  {idea.source_link.url && (
                    <>
                      {' \u2014 '}
                      <StyledLink
                        href={idea.source_link.url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {idea.source_link.url}
                      </StyledLink>
                    </>
                  )}
                </RowValue>
              </LabeledRow>
            )}
          </Section>

          {/* 7. Captions (conditional) */}
          {hasCaptions && (
            <Section>
              <SectionTitle>Captions</SectionTitle>
              {captions.map((cap) => (
                <CaptionBlock key={cap.label}>
                  <CaptionLabel>{cap.label}</CaptionLabel>
                  <CaptionText>{cap.value}</CaptionText>
                </CaptionBlock>
              ))}
            </Section>
          )}

          {/* 8. Dates (conditional) */}
          {hasDates && (
            <Section>
              <SectionTitle>Dates</SectionTitle>
              {idea.filmed_date && (
                <LabeledRow>
                  <RowLabel>Filmed</RowLabel>
                  <RowValue>{formatDate(idea.filmed_date)}</RowValue>
                </LabeledRow>
              )}
              {idea.posted_date && (
                <LabeledRow>
                  <RowLabel>Posted</RowLabel>
                  <RowValue>{formatDate(idea.posted_date)}</RowValue>
                </LabeledRow>
              )}
              {postUrlEntries.length > 0 && (
                <LabeledRow>
                  <RowLabel>Post URLs</RowLabel>
                  <RowValue>
                    {postUrlEntries.map(([platform, url]) => (
                      <div key={platform} style={{ marginBottom: '4px' }}>
                        <span style={{ textTransform: 'capitalize' }}>{platform}</span>{' \u2014 '}
                        <StyledLink href={url} target="_blank" rel="noopener noreferrer">
                          {url}
                        </StyledLink>
                      </div>
                    ))}
                  </RowValue>
                </LabeledRow>
              )}
            </Section>
          )}
        </PanelContent>
      </Panel>
    </>
  )
}

export default IdeaDetail

import { useState, useEffect, useMemo } from 'react'
import styled, { useTheme } from 'styled-components'

const Bar = styled.div`
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.md};
  padding: ${({ theme }) => theme.spacing.md};
  margin-bottom: ${({ theme }) => theme.spacing.lg};
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
`

const Group = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.xs};
  flex-wrap: wrap;
`

const Label = styled.span`
  font-size: ${({ theme }) => theme.fontSize.sm};
  color: ${({ theme }) => theme.colors.textMuted};
  white-space: nowrap;
`

const Select = styled.select`
  background: ${({ theme }) => theme.colors.bg};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.sm};
  color: ${({ theme }) => theme.colors.text};
  font-size: ${({ theme }) => theme.fontSize.sm};
  padding: 4px 8px;
  cursor: pointer;
  outline: none;
  &:focus {
    border-color: ${({ theme }) => theme.colors.accent};
  }
`

const ToggleButton = styled.button`
  background: ${({ theme }) => theme.colors.bg};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.sm};
  color: ${({ theme }) => theme.colors.text};
  font-size: ${({ theme }) => theme.fontSize.sm};
  padding: 4px 8px;
  cursor: pointer;
  line-height: 1;
  &:hover {
    background: ${({ theme }) => theme.colors.surfaceHover};
  }
`

const Pill = styled.button`
  background: ${({ $active, $color, theme }) =>
    $active ? $color : theme.colors.bg};
  border: 1px solid ${({ $active, $color, theme }) =>
    $active ? $color : theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.sm};
  color: ${({ $active, theme }) =>
    $active ? '#fff' : theme.colors.textMuted};
  font-size: ${({ theme }) => theme.fontSize.sm};
  padding: 2px 10px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
  &:hover {
    background: ${({ $active, $color, theme }) =>
      $active ? $color : theme.colors.surfaceHover};
  }
`

const SearchInput = styled.input`
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.sm};
  color: ${({ theme }) => theme.colors.text};
  font-size: ${({ theme }) => theme.fontSize.sm};
  padding: 4px 8px;
  width: 160px;
  outline: none;
  &:focus {
    border-color: ${({ theme }) => theme.colors.accent};
  }
  &::placeholder {
    color: ${({ theme }) => theme.colors.textMuted};
  }
`

const CheckLabel = styled.label`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.xs};
  font-size: ${({ theme }) => theme.fontSize.sm};
  color: ${({ theme }) => theme.colors.textMuted};
  cursor: pointer;
  white-space: nowrap;
`

const ClearButton = styled.button`
  background: transparent;
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.sm};
  color: ${({ theme }) => theme.colors.textMuted};
  font-size: ${({ theme }) => theme.fontSize.xs};
  padding: 2px 8px;
  cursor: pointer;
  white-space: nowrap;
  &:hover {
    color: ${({ theme }) => theme.colors.text};
    border-color: ${({ theme }) => theme.colors.text};
  }
`

const Separator = styled.div`
  width: 1px;
  height: 24px;
  background: ${({ theme }) => theme.colors.border};
  margin: 0 ${({ theme }) => theme.spacing.xs};
`

const STATUSES = ['new', 'queued', 'filming_today', 'filmed', 'captioned', 'posted', 'archived']
const FILMING_SETUPS = ['talking_head', 'screen_recording', 'walk_and_talk', 'studio', 'split_screen_react']

function formatLabel(value) {
  return value.replace(/_/g, ' ')
}

function FilterBar({ filters, onFilterChange, ideas }) {
  const theme = useTheme()
  const [searchText, setSearchText] = useState(filters.search || '')

  // Derive setup colors from theme: cycle through status palette for setups
  const SETUP_COLORS = {
    talking_head: theme.colors.status.new,
    screen_recording: theme.colors.status.queued,
    walk_and_talk: theme.colors.status.filming_today,
    studio: theme.colors.status.filmed,
    split_screen_react: theme.colors.accent,
  }

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchText !== filters.search) {
        onFilterChange({ search: searchText })
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [searchText, filters.search, onFilterChange])

  // Sync external search changes
  useEffect(() => {
    setSearchText(filters.search || '')
  }, [filters.search])

  const uniqueFormats = useMemo(() => {
    if (!ideas || ideas.length === 0) return []
    const formats = new Set()
    ideas.forEach((idea) => {
      if (idea.format) formats.add(idea.format)
    })
    return Array.from(formats).sort()
  }, [ideas])

  const activeStatuses = filters.status ? filters.status.split(',') : []
  const activeSetups = filters.filming_setup ? filters.filming_setup.split(',') : []

  function togglePill(current, value) {
    const arr = current ? current.split(',') : []
    const idx = arr.indexOf(value)
    if (idx >= 0) {
      arr.splice(idx, 1)
    } else {
      arr.push(value)
    }
    return arr.filter(Boolean).join(',')
  }

  function handleClear() {
    setSearchText('')
    onFilterChange({
      status: '',
      sort: 'score',
      order: 'desc',
      filming_setup: '',
      format: '',
      top_pick: '',
      search: '',
    })
  }

  return (
    <Bar>
      <Group>
        <Label>Sort</Label>
        <Select
          value={filters.sort}
          onChange={(e) => onFilterChange({ sort: e.target.value })}
        >
          <option value="score">Score</option>
          <option value="name">Name</option>
          <option value="status">Status</option>
          <option value="urgency">Urgency</option>
        </Select>
        <ToggleButton
          onClick={() =>
            onFilterChange({ order: filters.order === 'desc' ? 'asc' : 'desc' })
          }
          title={filters.order === 'desc' ? 'Descending' : 'Ascending'}
        >
          {filters.order === 'desc' ? '\u2193' : '\u2191'}
        </ToggleButton>
      </Group>

      <Separator />

      <Group>
        <Label>Status</Label>
        {STATUSES.map((s) => (
          <Pill
            key={s}
            $active={activeStatuses.includes(s)}
            $color={theme.colors.status[s]}
            onClick={() =>
              onFilterChange({ status: togglePill(filters.status, s) })
            }
          >
            {formatLabel(s)}
          </Pill>
        ))}
      </Group>

      <Separator />

      <Group>
        <Label>Setup</Label>
        {FILMING_SETUPS.map((s) => (
          <Pill
            key={s}
            $active={activeSetups.includes(s)}
            $color={SETUP_COLORS[s]}
            onClick={() =>
              onFilterChange({ filming_setup: togglePill(filters.filming_setup, s) })
            }
          >
            {formatLabel(s)}
          </Pill>
        ))}
      </Group>

      <Separator />

      <Group>
        <Label>Format</Label>
        <Select
          value={filters.format}
          onChange={(e) => onFilterChange({ format: e.target.value })}
        >
          <option value="">All</option>
          {uniqueFormats.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </Select>
      </Group>

      <Separator />

      <CheckLabel>
        <input
          type="checkbox"
          checked={filters.top_pick === 'true'}
          onChange={(e) =>
            onFilterChange({ top_pick: e.target.checked ? 'true' : '' })
          }
        />
        Top Picks
      </CheckLabel>

      <Separator />

      <SearchInput
        type="text"
        placeholder="Search..."
        value={searchText}
        onChange={(e) => setSearchText(e.target.value)}
      />

      <ClearButton onClick={handleClear}>Clear</ClearButton>
    </Bar>
  )
}

export default FilterBar

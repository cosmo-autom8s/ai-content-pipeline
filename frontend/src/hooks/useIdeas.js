import { useState, useEffect, useCallback } from 'react'

const DEFAULT_FILTERS = {
  status: '',
  sort: 'score',
  order: 'desc',
  filming_setup: '',
  format: '',
  top_pick: '',
  search: '',
}

export function useIdeas() {
  const [ideas, setIdeas] = useState([])
  const [selectedIdea, setSelectedIdea] = useState(null)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [filters, setFilters] = useState(DEFAULT_FILTERS)

  const fetchIdeas = useCallback(async (currentFilters) => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      for (const [key, value] of Object.entries(currentFilters)) {
        if (value !== '' && value !== null && value !== undefined) {
          // Map frontend 'format' key to API 'idea_format' param
          const apiKey = key === 'format' ? 'idea_format' : key
          params.append(apiKey, value)
        }
      }
      const query = params.toString()
      const url = `/api/ideas${query ? `?${query}` : ''}`
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      const data = await response.json()
      setIdeas(data)
    } catch (err) {
      setError(err.message)
      // Keep stale ideas visible — do not clear them
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch('/api/stats')
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      const data = await response.json()
      setStats(data)
    } catch (err) {
      setError(err.message)
    }
  }, [])

  const selectIdea = useCallback(async (id) => {
    setError(null)
    try {
      const response = await fetch(`/api/ideas/${id}`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      const data = await response.json()
      setSelectedIdea(data)
    } catch (err) {
      setError(err.message)
    }
  }, [])

  const closeDetail = useCallback(() => {
    setSelectedIdea(null)
  }, [])

  const updateFilters = useCallback((newFilters) => {
    setFilters((prev) => ({ ...prev, ...newFilters }))
  }, [])

  // Fetch ideas on mount and whenever filters change
  useEffect(() => {
    fetchIdeas(filters)
  }, [filters, fetchIdeas])

  // Fetch stats on mount
  useEffect(() => {
    fetchStats()
  }, [fetchStats])

  return {
    ideas,
    selectedIdea,
    stats,
    loading,
    error,
    filters,
    fetchIdeas: () => fetchIdeas(filters),
    selectIdea,
    closeDetail,
    updateFilters,
    fetchStats,
  }
}

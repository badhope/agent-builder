import { useState, useEffect, useCallback } from 'react'
import { View, Text, ScrollView } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useAuth } from '@/stores/auth'
import { convertApi } from '@/api/convert'
import type { Task } from '@/types/api'
import { formatDate, getStateLabel, getStateBadgeClass, formatFormatName } from '@/utils/format'
import './tasks.scss'

const STATE_FILTERS = [
  { label: '全部', value: '' },
  { label: '排队中', value: 'queued' },
  { label: '转换中', value: 'running' },
  { label: '已完成', value: 'succeeded' },
  { label: '失败', value: 'failed' }
]

export default function TasksPage() {
  const { isLoggedIn } = useAuth()
  const [tasks, setTasks] = useState<Task[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [stateFilter, setStateFilter] = useState('')

  useEffect(() => {
    if (!isLoggedIn) {
      Taro.redirectTo({ url: '/pages/login/index' })
      return
    }
    loadTasks()
  }, [isLoggedIn, stateFilter])

  const loadTasks = async () => {
    setLoading(true)
    try {
      const params: Record<string, any> = { limit: 50 }
      if (stateFilter) params.state = stateFilter
      const data = await convertApi.listTasks(params)
      setTasks(data.items || [])
      setTotal(data.total || 0)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  const handleTaskClick = (task: Task) => {
    Taro.navigateTo({ url: `/pages/task-detail/index?id=${task.id}` })
  }

  if (!isLoggedIn) return null

  return (
    <View className='container tasks-page'>
      <ScrollView className='filter-scroll' scrollX>
        <View className='filter-list'>
          {STATE_FILTERS.map(f => (
            <View
              key={f.value}
              className={`filter-item ${stateFilter === f.value ? 'filter-active' : ''}`}
              onClick={() => setStateFilter(f.value)}
            >
              <Text>{f.label}</Text>
            </View>
          ))}
        </View>
      </ScrollView>

      {loading ? (
        <View className='loading-spinner'>
          <Text className='text-gray'>加载中...</Text>
        </View>
      ) : tasks.length === 0 ? (
        <View className='empty-state'>
          <Text className='empty-icon'>📋</Text>
          <Text className='empty-text'>暂无转换任务</Text>
          <Text className='text-sm text-gray mt-16'>去转换页面开始第一个任务吧</Text>
        </View>
      ) : (
        <View className='task-list'>
          {tasks.map(task => (
            <View key={task.id} className='task-card' onClick={() => handleTaskClick(task)}>
              <View className='task-header'>
                <Text className='task-name'>{task.source_filename}</Text>
                <Text className={`badge ${getStateBadgeClass(task.state)}`}>
                  {getStateLabel(task.state)}
                </Text>
              </View>
              <View className='task-conversion'>
                <Text className='text-sm text-gray'>
                  {formatFormatName(task.source_format)} → {formatFormatName(task.target_format)}
                </Text>
              </View>
              {task.progress_pct !== undefined && task.progress_pct !== null && task.state === 'running' && (
                <View className='progress-bar'>
                  <View className='progress-fill' style={{ width: `${task.progress_pct}%` }} />
                </View>
              )}
              <View className='task-footer'>
                <Text className='text-sm text-gray'>{formatDate(task.created_at)}</Text>
                {task.error_message && (
                  <Text className='text-sm text-danger'>{task.error_message.slice(0, 30)}</Text>
                )}
              </View>
            </View>
          ))}
        </View>
      )}
    </View>
  )
}
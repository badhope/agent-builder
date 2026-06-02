import { useState, useEffect, useCallback } from 'react'
import { View, Text } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import { convertApi } from '@/api/convert'
import type { Task } from '@/types/api'
import { formatDate, getStateLabel, getStateBadgeClass, formatFormatName, formatFileSize } from '@/utils/format'
import './task-detail.scss'

export default function TaskDetailPage() {
  const router = useRouter()
  const { id } = router.params
  const [task, setTask] = useState<Task | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)

  useEffect(() => {
    if (id) loadTask()
  }, [id])

  const loadTask = async () => {
    if (!id) return
    setLoading(true)
    try {
      const data = await convertApi.getTask(id)
      setTask(data)
    } catch {
      Taro.showToast({ title: '加载失败', icon: 'none' })
    } finally {
      setLoading(false)
    }
  }

  const handleRetry = async () => {
    if (!id) return
    setActionLoading(true)
    try {
      const data = await convertApi.retryTask(id)
      setTask(data)
      Taro.showToast({ title: '已重新提交', icon: 'success' })
    } catch {
      // handled in api client
    } finally {
      setActionLoading(false)
    }
  }

  const handleCancel = async () => {
    if (!id) return
    setActionLoading(true)
    try {
      const data = await convertApi.cancelTask(id)
      setTask(data)
      Taro.showToast({ title: '已取消', icon: 'success' })
    } catch {
      // handled in api client
    } finally {
      setActionLoading(false)
    }
  }

  const handleDownload = () => {
    if (!task?.output_file_id) return
    Taro.showToast({ title: '下载功能开发中', icon: 'none' })
  }

  if (loading) {
    return (
      <View className='container'>
        <View className='loading-spinner'>
          <Text className='text-gray'>加载中...</Text>
        </View>
      </View>
    )
  }

  if (!task) {
    return (
      <View className='container'>
        <View className='empty-state'>
          <Text className='empty-text'>任务不存在</Text>
        </View>
      </View>
    )
  }

  return (
    <View className='container task-detail-page'>
      <View className='card'>
        <View className='detail-header'>
          <Text className='detail-title'>转换详情</Text>
          <Text className={`badge badge-lg ${getStateBadgeClass(task.state)}`}>
            {getStateLabel(task.state)}
          </Text>
        </View>

        <View className='detail-row'>
          <Text className='detail-label'>文件名</Text>
          <Text className='detail-value'>{task.source_filename}</Text>
        </View>
        <View className='detail-row'>
          <Text className='detail-label'>转换格式</Text>
          <Text className='detail-value'>
            {formatFormatName(task.source_format)} → {formatFormatName(task.target_format)}
          </Text>
        </View>
        {task.progress_pct !== undefined && task.progress_pct !== null && task.state === 'running' && (
          <View className='detail-row'>
            <Text className='detail-label'>进度</Text>
            <View className='progress-wrap'>
              <View className='progress-bar'>
                <View className='progress-fill' style={{ width: `${task.progress_pct}%` }} />
              </View>
              <Text className='progress-text'>{task.progress_pct}%</Text>
            </View>
          </View>
        )}
        <View className='detail-row'>
          <Text className='detail-label'>优先级</Text>
          <Text className='detail-value'>{task.priority}</Text>
        </View>
        <View className='detail-row'>
          <Text className='detail-label'>创建时间</Text>
          <Text className='detail-value'>{formatDate(task.created_at)}</Text>
        </View>
        {task.started_at && (
          <View className='detail-row'>
            <Text className='detail-label'>开始时间</Text>
            <Text className='detail-value'>{formatDate(task.started_at)}</Text>
          </View>
        )}
        {task.finished_at && (
          <View className='detail-row'>
            <Text className='detail-label'>完成时间</Text>
            <Text className='detail-value'>{formatDate(task.finished_at)}</Text>
          </View>
        )}
        {task.output_size !== undefined && task.output_size !== null && (
          <View className='detail-row'>
            <Text className='detail-label'>输出大小</Text>
            <Text className='detail-value'>{formatFileSize(task.output_size)}</Text>
          </View>
        )}
        <View className='detail-row'>
          <Text className='detail-label'>尝试次数</Text>
          <Text className='detail-value'>{task.attempts}/{task.max_attempts}</Text>
        </View>
      </View>

      {task.error_message && (
        <View className='card error-card'>
          <Text className='error-title'>错误信息</Text>
          <Text className='error-message'>{task.error_message}</Text>
          {task.error_code && (
            <Text className='error-code'>错误码: {task.error_code}</Text>
          )}
        </View>
      )}

      <View className='action-section'>
        {task.state === 'failed' && (
          <View className={`btn-primary ${actionLoading ? 'btn-disabled' : ''}`} onClick={handleRetry}>
            {actionLoading ? '处理中...' : '重试转换'}
          </View>
        )}
        {(task.state === 'queued' || task.state === 'running') && (
          <View className={`btn-outline ${actionLoading ? 'btn-disabled' : ''}`} onClick={handleCancel}>
            {actionLoading ? '处理中...' : '取消任务'}
          </View>
        )}
        {task.state === 'succeeded' && task.output_file_id && (
          <View className='btn-primary' onClick={handleDownload}>
            下载结果文件
          </View>
        )}
        <View className='btn-outline mt-24' onClick={() => loadTask()}>
          刷新状态
        </View>
      </View>
    </View>
  )
}
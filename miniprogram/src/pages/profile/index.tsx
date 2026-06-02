import { useEffect } from 'react'
import { View, Text } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useAuth } from '@/stores/auth'
import './profile.scss'

export default function ProfilePage() {
  const { isLoggedIn, user, isLoading, logout } = useAuth()

  useEffect(() => {
    if (!isLoggedIn && !isLoading) {
      Taro.redirectTo({ url: '/pages/login/index' })
    }
  }, [isLoggedIn, isLoading])

  const handleLogout = () => {
    Taro.showModal({
      title: '提示',
      content: '确定要退出登录吗？',
      success: (res) => {
        if (res.confirm) {
          logout()
          Taro.showToast({ title: '已退出', icon: 'success' })
          setTimeout(() => {
            Taro.reLaunch({ url: '/pages/index/index' })
          }, 500)
        }
      }
    })
  }

  const handleLogin = () => {
    Taro.navigateTo({ url: '/pages/login/index' })
  }

  if (isLoading) {
    return (
      <View className='container'>
        <View className='loading-spinner'>
          <Text className='text-gray'>加载中...</Text>
        </View>
      </View>
    )
  }

  if (!isLoggedIn) {
    return (
      <View className='container profile-page'>
        <View className='card'>
          <View className='text-center'>
            <Text className='profile-avatar-icon'>👤</Text>
            <Text className='profile-empty-title'>未登录</Text>
            <Text className='profile-empty-desc'>登录后可使用全部功能</Text>
            <View className='btn-primary mt-32' onClick={handleLogin}>
              立即登录
            </View>
          </View>
        </View>
      </View>
    )
  }

  return (
    <View className='container profile-page'>
      <View className='card user-card'>
        <View className='user-header'>
          <View className='user-avatar'>
            <Text className='avatar-text'>
              {(user?.name || user?.email || 'U').charAt(0).toUpperCase()}
            </Text>
          </View>
          <View className='user-info'>
            <Text className='user-name'>{user?.name || user?.email}</Text>
            <Text className='user-email'>{user?.email}</Text>
          </View>
        </View>
        <View className='user-stats'>
          <View className='stat-item'>
            <Text className='stat-value'>{user?.quota_used || 0}</Text>
            <Text className='stat-label'>已用配额</Text>
          </View>
          <View className='stat-divider' />
          <View className='stat-item'>
            <Text className='stat-value'>{user?.quota_total || 0}</Text>
            <Text className='stat-label'>总配额</Text>
          </View>
        </View>
      </View>

      <View className='menu-section'>
        <View className='menu-item' onClick={() => Taro.switchTab({ url: '/pages/tasks/index' })}>
          <Text className='menu-label'>我的任务</Text>
          <Text className='menu-arrow'>›</Text>
        </View>
        <View className='menu-item' onClick={() => Taro.switchTab({ url: '/pages/convert/index' })}>
          <Text className='menu-label'>文档转换</Text>
          <Text className='menu-arrow'>›</Text>
        </View>
      </View>

      <View className='menu-section'>
        <View className='menu-item menu-danger' onClick={handleLogout}>
          <Text className='menu-label'>退出登录</Text>
        </View>
      </View>

      <View className='version-info'>
        <Text className='text-sm text-gray'>DocFormatConverter v1.0.0</Text>
      </View>
    </View>
  )
}
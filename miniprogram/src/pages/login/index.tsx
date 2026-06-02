import { useState } from 'react'
import { View, Text, Input, Button } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useAuth } from '@/stores/auth'
import './login.scss'

export default function LoginPage() {
  const { login, isLoggedIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  if (isLoggedIn) {
    Taro.switchTab({ url: '/pages/convert/index' })
    return null
  }

  const handleLogin = async () => {
    if (!email.trim()) {
      Taro.showToast({ title: '请输入邮箱', icon: 'none' })
      return
    }
    if (!password) {
      Taro.showToast({ title: '请输入密码', icon: 'none' })
      return
    }
    setLoading(true)
    try {
      await login(email.trim(), password)
      Taro.showToast({ title: '登录成功', icon: 'success' })
      setTimeout(() => {
        Taro.switchTab({ url: '/pages/convert/index' })
      }, 500)
    } catch {
      // error toast handled in api client
    } finally {
      setLoading(false)
    }
  }

  return (
    <View className='container login-page'>
      <View className='login-card'>
        <Text className='login-title'>欢迎回来</Text>
        <Text className='login-subtitle'>登录您的账号以继续使用</Text>

        <View className='form-group'>
          <Text className='form-label'>邮箱</Text>
          <Input
            className='input-field'
            type='text'
            placeholder='请输入邮箱地址'
            value={email}
            onInput={e => setEmail(e.detail.value)}
          />
        </View>

        <View className='form-group'>
          <Text className='form-label'>密码</Text>
          <Input
            className='input-field'
            type='password'
            placeholder='请输入密码'
            value={password}
            onInput={e => setPassword(e.detail.value)}
          />
        </View>

        <View className={`btn-primary ${loading ? 'btn-disabled' : ''}`} onClick={handleLogin}>
          {loading ? '登录中...' : '登录'}
        </View>

        <View className='login-footer'>
          <Text className='text-gray'>还没有账号？</Text>
          <Text className='text-primary' onClick={() => Taro.redirectTo({ url: '/pages/register/index' })}>
            立即注册
          </Text>
        </View>
      </View>
    </View>
  )
}
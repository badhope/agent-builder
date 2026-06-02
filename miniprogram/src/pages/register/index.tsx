import { useState } from 'react'
import { View, Text, Input } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useAuth } from '@/stores/auth'
import './register.scss'

export default function RegisterPage() {
  const { register, isLoggedIn } = useAuth()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)

  if (isLoggedIn) {
    Taro.switchTab({ url: '/pages/convert/index' })
    return null
  }

  const handleRegister = async () => {
    if (!email.trim()) {
      Taro.showToast({ title: '请输入邮箱', icon: 'none' })
      return
    }
    if (!password) {
      Taro.showToast({ title: '请输入密码', icon: 'none' })
      return
    }
    if (password.length < 8) {
      Taro.showToast({ title: '密码至少8位', icon: 'none' })
      return
    }
    if (password !== confirmPassword) {
      Taro.showToast({ title: '两次密码不一致', icon: 'none' })
      return
    }
    setLoading(true)
    try {
      await register(email.trim(), password, name.trim() || undefined)
      Taro.showToast({ title: '注册成功', icon: 'success' })
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
    <View className='container register-page'>
      <View className='register-card'>
        <Text className='register-title'>创建账号</Text>
        <Text className='register-subtitle'>注册即可开始文档转换</Text>

        <View className='form-group'>
          <Text className='form-label'>昵称（选填）</Text>
          <Input
            className='input-field'
            type='text'
            placeholder='请输入昵称'
            value={name}
            onInput={e => setName(e.detail.value)}
          />
        </View>

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
            placeholder='请输入密码（至少8位）'
            value={password}
            onInput={e => setPassword(e.detail.value)}
          />
        </View>

        <View className='form-group'>
          <Text className='form-label'>确认密码</Text>
          <Input
            className='input-field'
            type='password'
            placeholder='请再次输入密码'
            value={confirmPassword}
            onInput={e => setConfirmPassword(e.detail.value)}
          />
        </View>

        <View className={`btn-primary ${loading ? 'btn-disabled' : ''}`} onClick={handleRegister}>
          {loading ? '注册中...' : '注册'}
        </View>

        <View className='register-footer'>
          <Text className='text-gray'>已有账号？</Text>
          <Text className='text-primary' onClick={() => Taro.redirectTo({ url: '/pages/login/index' })}>
            立即登录
          </Text>
        </View>
      </View>
    </View>
  )
}
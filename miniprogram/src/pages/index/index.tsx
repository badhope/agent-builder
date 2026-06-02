import { View, Text, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useAuth } from '@/stores/auth'
import './index.scss'

export default function IndexPage() {
  const { isLoggedIn, user } = useAuth()

  const handleStart = () => {
    if (isLoggedIn) {
      Taro.switchTab({ url: '/pages/convert/index' })
    } else {
      Taro.navigateTo({ url: '/pages/login/index' })
    }
  }

  return (
    <View className='container index-page'>
      <View className='hero'>
        <Text className='hero-title'>DocFormatConverter</Text>
        <Text className='hero-subtitle'>专业的文档格式转换平台</Text>
        <Text className='hero-desc'>
          支持 PDF、Word、Excel、PPT、Markdown、HTML、EPUB 等数十种格式相互转换
        </Text>
      </View>

      <View className='features'>
        <View className='feature-item'>
          <Text className='feature-icon'>📄</Text>
          <Text className='feature-title'>文档转换</Text>
          <Text className='feature-desc'>PDF ↔ Word ↔ ODT 等办公文档格式互转</Text>
        </View>
        <View className='feature-item'>
          <Text className='feature-icon'>📊</Text>
          <Text className='feature-title'>表格处理</Text>
          <Text className='feature-desc'>XLSX ↔ CSV 等电子表格格式转换</Text>
        </View>
        <View className='feature-item'>
          <Text className='feature-icon'>📝</Text>
          <Text className='feature-title'>标记语言</Text>
          <Text className='feature-desc'>Markdown ↔ HTML 等标记语言互转</Text>
        </View>
        <View className='feature-item'>
          <Text className='feature-icon'>🖼️</Text>
          <Text className='feature-title'>图片处理</Text>
          <Text className='feature-desc'>PNG ↔ JPG ↔ WebP 等图片格式转换</Text>
        </View>
        <View className='feature-item'>
          <Text className='feature-icon'>📚</Text>
          <Text className='feature-title'>电子书</Text>
          <Text className='feature-desc'>EPUB ↔ MOBI 等电子书格式转换</Text>
        </View>
        <View className='feature-item'>
          <Text className='feature-icon'>📋</Text>
          <Text className='feature-title'>数据格式</Text>
          <Text className='feature-desc'>JSON ↔ YAML ↔ XML ↔ CSV 等数据格式互转</Text>
        </View>
      </View>

      <View className='action-section'>
        <View className='btn-primary' onClick={handleStart}>
          {isLoggedIn ? `欢迎回来，${user?.name || user?.email}` : '立即开始'}
        </View>
        {isLoggedIn && (
          <View className='btn-outline mt-24' onClick={() => Taro.switchTab({ url: '/pages/tasks/index' })}>
            查看我的任务
          </View>
        )}
      </View>
    </View>
  )
}
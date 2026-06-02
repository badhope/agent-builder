import { View, Text } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useState, useEffect } from 'react'
import './index.scss'

const TAB_LIST = [
  { pagePath: 'pages/index/index', text: '首页', icon: '🏠' },
  { pagePath: 'pages/convert/index', text: '转换', icon: '🔄' },
  { pagePath: 'pages/tasks/index', text: '任务', icon: '📋' },
  { pagePath: 'pages/profile/index', text: '我的', icon: '👤' }
]

export default function CustomTabBar() {
  const [current, setCurrent] = useState(0)

  useEffect(() => {
    const pages = Taro.getCurrentPages()
    const page = pages[pages.length - 1]
    if (page) {
      const route = page.route || ''
      const idx = TAB_LIST.findIndex(t => t.pagePath === route)
      if (idx >= 0) setCurrent(idx)
    }
  }, [])

  const handleTabClick = (index: number, path: string) => {
    setCurrent(index)
    Taro.switchTab({ url: `/${path}` })
  }

  return (
    <View className='custom-tabbar'>
      {TAB_LIST.map((tab, idx) => (
        <View
          key={tab.pagePath}
          className={`tabbar-item ${idx === current ? 'tabbar-active' : ''}`}
          onClick={() => handleTabClick(idx, tab.pagePath)}
        >
          <Text className='tabbar-icon'>{tab.icon}</Text>
          <Text className='tabbar-text'>{tab.text}</Text>
        </View>
      ))}
    </View>
  )
}
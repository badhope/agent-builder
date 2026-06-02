import { PropsWithChildren } from 'react'
import Taro from '@tarojs/taro'
import './app.scss'

const API_BASE = 'http://localhost:8000/api'

export { API_BASE }

export default function App({ children }: PropsWithChildren) {
  return children
}
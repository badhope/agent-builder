import { useState, useEffect, useCallback } from 'react'
import { View, Text, ScrollView } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useAuth } from '@/stores/auth'
import { convertApi } from '@/api/convert'
import type { FileMeta, Task, ConversionFormat } from '@/types/api'
import { formatFileSize, formatFormatName } from '@/utils/format'
import './convert.scss'

const CATEGORY_MAP: Record<string, string> = {
  document: '文档',
  spreadsheet: '表格',
  presentation: '演示',
  image: '图片',
  markup: '标记语言',
  data: '数据',
  ebook: '电子书'
}

export default function ConvertPage() {
  const { isLoggedIn } = useAuth()
  const [formats, setFormats] = useState<ConversionFormat[]>([])
  const [sourceFile, setSourceFile] = useState<FileMeta | null>(null)
  const [targetFormat, setTargetFormat] = useState('')
  const [loading, setLoading] = useState(false)
  const [currentTask, setCurrentTask] = useState<Task | null>(null)
  const [selectedCategory, setSelectedCategory] = useState('')

  useEffect(() => {
    if (!isLoggedIn) {
      Taro.redirectTo({ url: '/pages/login/index' })
      return
    }
    loadFormats()
  }, [isLoggedIn])

  const loadFormats = async () => {
    try {
      const data = await convertApi.getFormats()
      setFormats(data.conversions || [])
    } catch {
      // ignore
    }
  }

  const handleChooseFile = useCallback(async () => {
    if (!isLoggedIn) {
      Taro.showToast({ title: '请先登录', icon: 'none' })
      return
    }
    try {
      const res = await Taro.chooseMessageFile({
        count: 1,
        type: 'file'
      })
      if (res.tempFiles.length > 0) {
        const file = res.tempFiles[0]
        Taro.showLoading({ title: '上传中...' })
        try {
          const uploaded = await convertApi.upload(file.path)
          setSourceFile(uploaded)
          setTargetFormat('')
          setCurrentTask(null)
          setSelectedCategory('')
          Taro.hideLoading()
          Taro.showToast({ title: '上传成功', icon: 'success' })
        } catch {
          Taro.hideLoading()
        }
      }
    } catch {
      // user cancelled
    }
  }, [isLoggedIn])

  const getAvailableTargets = useCallback((): ConversionFormat[] => {
    if (!sourceFile) return []
    const src = sourceFile.format?.toLowerCase() || ''
    return formats.filter(f => f.source === src)
  }, [sourceFile, formats])

  const getCategories = useCallback((): string[] => {
    const targets = getAvailableTargets()
    const cats = new Set<string>()
    targets.forEach(t => {
      const cat = getCategoryForFormat(t.target)
      if (cat) cats.add(cat)
    })
    return Array.from(cats)
  }, [getAvailableTargets])

  const getFilteredTargets = useCallback((): ConversionFormat[] => {
    const targets = getAvailableTargets()
    if (!selectedCategory) return targets
    return targets.filter(t => getCategoryForFormat(t.target) === selectedCategory)
  }, [getAvailableTargets, selectedCategory])

  const handleConvert = async () => {
    if (!sourceFile || !targetFormat) return
    setLoading(true)
    try {
      const task = await convertApi.convert(sourceFile.id, targetFormat)
      setCurrentTask(task)
      Taro.showToast({ title: '任务已提交', icon: 'success' })
    } catch {
      // error toast handled in api client
    } finally {
      setLoading(false)
    }
  }

  const handleViewTask = () => {
    if (currentTask) {
      Taro.navigateTo({ url: `/pages/task-detail/index?id=${currentTask.id}` })
    } else {
      Taro.switchTab({ url: '/pages/tasks/index' })
    }
  }

  if (!isLoggedIn) return null

  return (
    <View className='container convert-page'>
      <View className='section'>
        <Text className='section-title'>上传文件</Text>
        {sourceFile ? (
          <View className='file-card'>
            <View className='file-info'>
              <Text className='file-name'>{sourceFile.filename}</Text>
              <Text className='file-meta'>
                {formatFileSize(sourceFile.size)} · {formatFormatName(sourceFile.format || '')}
              </Text>
            </View>
            <View className='file-actions'>
              <Text className='text-danger' onClick={() => {
                setSourceFile(null)
                setTargetFormat('')
                setCurrentTask(null)
              }}>删除</Text>
              <Text className='text-primary' onClick={handleChooseFile}>重新选择</Text>
            </View>
          </View>
        ) : (
          <View className='upload-area' onClick={handleChooseFile}>
            <Text className='upload-icon'>📁</Text>
            <Text className='upload-text'>点击选择文件</Text>
            <Text className='upload-hint'>支持 PDF、Word、Excel、PPT、图片等格式</Text>
          </View>
        )}
      </View>

      {sourceFile && (
        <View className='section'>
          <Text className='section-title'>选择目标格式</Text>
          {getCategories().length > 0 && (
            <ScrollView className='category-scroll' scrollX>
              <View className='category-list'>
                <View
                  className={`category-item ${selectedCategory === '' ? 'category-active' : ''}`}
                  onClick={() => setSelectedCategory('')}
                >
                  <Text>全部</Text>
                </View>
                {getCategories().map(cat => (
                  <View
                    key={cat}
                    className={`category-item ${selectedCategory === cat ? 'category-active' : ''}`}
                    onClick={() => setSelectedCategory(cat)}
                  >
                    <Text>{cat}</Text>
                  </View>
                ))}
              </View>
            </ScrollView>
          )}
          <View className='format-grid'>
            {getFilteredTargets().length === 0 ? (
              <View className='empty-state'>
                <Text className='empty-text'>暂无可转换的目标格式</Text>
              </View>
            ) : (
              getFilteredTargets().map(f => (
                <View
                  key={f.target}
                  className={`format-item ${targetFormat === f.target ? 'format-selected' : ''}`}
                  onClick={() => setTargetFormat(f.target)}
                >
                  <Text className='format-name'>{formatFormatName(f.target)}</Text>
                  <Text className='format-quality'>
                    {'★'.repeat(f.quality)}{'☆'.repeat(5 - f.quality)}
                  </Text>
                </View>
              ))
            )}
          </View>
        </View>
      )}

      {sourceFile && targetFormat && (
        <View className='section'>
          <View className={`btn-primary ${loading ? 'btn-disabled' : ''}`} onClick={handleConvert}>
            {loading ? '提交中...' : `开始转换: ${formatFormatName(sourceFile.format || '')} → ${formatFormatName(targetFormat)}`}
          </View>
        </View>
      )}

      {currentTask && (
        <View className='section'>
          <View className='task-result-card'>
            <Text className='result-title'>转换任务已提交</Text>
            <View className='result-row'>
              <Text className='result-label'>状态</Text>
              <Text className={`badge badge-blue`}>排队中</Text>
            </View>
            <View className='result-row'>
              <Text className='result-label'>转换</Text>
              <Text className='text-base'>
                {formatFormatName(currentTask.source_format)} → {formatFormatName(currentTask.target_format)}
              </Text>
            </View>
            <View className='btn-outline mt-24' onClick={handleViewTask}>
              查看任务详情
            </View>
          </View>
        </View>
      )}

      <View className='section'>
        <Text className='section-title'>支持的转换格式</Text>
        <View className='category-grid'>
          {Object.entries(CATEGORY_MAP).map(([key, label]) => (
            <View key={key} className='category-card'>
              <Text className='category-label'>{label}</Text>
              <Text className='category-examples'>
                {getCategoryExamples(key)}
              </Text>
            </View>
          ))}
        </View>
      </View>
    </View>
  )
}

function getCategoryForFormat(fmt: string): string {
  const docFormats = ['pdf', 'docx', 'doc', 'odt', 'rtf', 'txt']
  const sheetFormats = ['xlsx', 'xls', 'csv', 'tsv', 'ods']
  const presFormats = ['pptx', 'ppt', 'odp']
  const imageFormats = ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'tiff', 'svg']
  const markupFormats = ['html', 'md', 'markdown', 'xml']
  const dataFormats = ['json', 'yaml', 'yml', 'csv']
  const ebookFormats = ['epub', 'mobi', 'azw3']

  if (docFormats.includes(fmt)) return 'document'
  if (sheetFormats.includes(fmt)) return 'spreadsheet'
  if (presFormats.includes(fmt)) return 'presentation'
  if (imageFormats.includes(fmt)) return 'image'
  if (markupFormats.includes(fmt)) return 'markup'
  if (dataFormats.includes(fmt)) return 'data'
  if (ebookFormats.includes(fmt)) return 'ebook'
  return ''
}

function getCategoryExamples(cat: string): string {
  const map: Record<string, string> = {
    document: 'PDF · DOCX · ODT · RTF · TXT',
    spreadsheet: 'XLSX · CSV · ODS',
    presentation: 'PPTX · ODP',
    image: 'PNG · JPG · WebP · GIF',
    markup: 'HTML · MD · XML',
    data: 'JSON · YAML · CSV',
    ebook: 'EPUB · MOBI'
  }
  return map[cat] || ''
}
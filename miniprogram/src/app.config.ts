export default defineAppConfig({
  pages: [
    'pages/index/index',
    'pages/login/index',
    'pages/register/index',
    'pages/convert/index',
    'pages/tasks/index',
    'pages/task-detail/index',
    'pages/profile/index'
  ],
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#1677ff',
    navigationBarTitleText: 'DocFormatConverter',
    navigationBarTextStyle: 'white'
  },
  tabBar: {
    custom: true,
    color: '#999999',
    selectedColor: '#1677ff',
    backgroundColor: '#ffffff',
    list: [
      { pagePath: 'pages/index/index', text: '首页' },
      { pagePath: 'pages/convert/index', text: '转换' },
      { pagePath: 'pages/tasks/index', text: '任务' },
      { pagePath: 'pages/profile/index', text: '我的' }
    ]
  }
})
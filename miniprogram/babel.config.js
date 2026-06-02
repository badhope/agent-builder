/** Taro babel config for the DocFormatConverter mini-program. */
module.exports = {
  presets: [
    ['taro', {
      framework: 'react',
      ts: true,
      useBuiltIns: 'usage',
      targets: { ios: '10', android: '6' }
    }]
  ],
  plugins: [
    ['@babel/plugin-proposal-decorators', { legacy: true }],
    ['@babel/plugin-proposal-class-properties', { loose: true }],
    ['@babel/plugin-transform-runtime', { corejs: false, helpers: true }]
  ]
}

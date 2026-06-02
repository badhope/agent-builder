module.exports = {
  env: {
    NODE_ENV: '"development"'
  },
  defineConstants: {},
  mini: {},
  h5: {
    devServer: {
      port: 10086,
      proxy: {
        '/api/': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          pathRewrite: { '^/api/': '/api/' }
        }
      }
    }
  }
}
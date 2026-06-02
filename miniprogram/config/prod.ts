/** Production Taro configuration for DocFormatConverter mini-program. */
module.exports = {
  env: {
    NODE_ENV: '"production"'
  },
  defineConstants: {
    'process.env.NODE_ENV': '"production"',
    'process.env.TARO_APP_API_BASE': JSON.stringify(process.env.TARO_APP_API_BASE || 'https://api.example.com/api'),
    'process.env.TARO_APP_NAME': JSON.stringify(process.env.TARO_APP_NAME || 'DocFormatConverter')
  },
  copy: {
    patterns: [],
    options: {}
  },
  mini: {
    minify: true,
    terser: {
      enable: true
    },
    postcss: {
      pxtransform: {
        enable: true,
        config: {}
      },
      url: {
        enable: true,
        config: { limit: 4096 }
      }
    }
  },
  h5: {
    publicPath: '/',
    staticDirectory: 'static',
    miniCssExtractPluginOption: {
      ignoreOrder: true
    },
    postcss: {
      autoprefixer: {
        enable: true,
        config: {}
      }
    },
    chainWebpack: (config) => {
      config.optimization.splitChunks({
        chunks: 'all',
        cacheGroups: {
          vendor: {
            test: /[\\/]node_modules[\\/]/,
            name: 'vendor',
            chunks: 'all'
          }
        }
      })
    }
  }
}

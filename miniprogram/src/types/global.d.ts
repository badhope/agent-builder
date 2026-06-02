declare module '*.png'
declare module '*.gif'
declare module '*.jpg'
declare module '*.jpeg'
declare module '*.svg'
declare module '*.css'
declare module '*.less'
declare module '*.scss'
declare module '*.sass'
declare module '*.styl'

declare const definePageConfig: (config: Record<string, any>) => Record<string, any>
declare const defineAppConfig: (config: Record<string, any>) => Record<string, any>

declare namespace JSX {
  interface IntrinsicElements {
    [elemName: string]: any
  }
}
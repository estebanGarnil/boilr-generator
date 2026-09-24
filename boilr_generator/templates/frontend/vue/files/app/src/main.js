import { createApp } from 'vue'
import App from './App.vue'
import { projectName } from './app-config.js'
import './style.css'

document.title = projectName
createApp(App).mount('#app')

<script setup>
import { ref } from 'vue'
import { projectName } from './app-config.js'
const count = ref(0)
</script>

<template>
  <main>
    <p class="eyebrow">BOILR / VUE + VITE</p>
    <h1>{{ projectName }}</h1>
    <p>Votre frontend est prêt. Modifiez <code>src/App.vue</code> pour commencer.</p>
    <button type="button" @click="count++">Compteur : {{ count }}</button>
    <p class="hint" aria-live="polite">Le compteur vérifie que Vue est bien actif.</p>
  </main>
</template>

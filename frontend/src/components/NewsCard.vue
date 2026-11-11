<script setup>
defineProps({
  article: { type: Object, required: true },
  featured: Boolean,
  chatBusy: Boolean,
})
defineEmits(['ask'])

const date = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium' })
</script>

<template>
  <article class="news-card" :class="{ featured }">
    <div v-if="article.image_url" class="news-image">
      <img :src="article.image_url" alt="" :loading="featured ? 'eager' : 'lazy'" />
    </div>
    <div class="news-copy">
      <p class="news-meta">
        <span>{{ article.category }}</span>
        <time v-if="article.published" :datetime="article.published">{{ date.format(new Date(article.published)) }}</time>
      </p>
      <h3>{{ article.title }}</h3>
      <p v-if="article.summary" class="news-summary">{{ article.summary }}</p>
      <div class="news-actions">
        <button class="secondary-button" :disabled="chatBusy" @click="$emit('ask', article)">Perguntar ao chat</button>
        <a class="text-button" :href="article.url" target="_blank" rel="noopener noreferrer">Ler na BBC ↗</a>
      </div>
    </div>
  </article>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({ client: { type: Object, required: true } })
const creating = ref(false)
const busy = ref(false)
const email = ref('')
const password = ref('')
const status = ref('')
const failed = ref(false)

function switchMode() {
  creating.value = !creating.value
  status.value = ''
  password.value = ''
}

async function submit() {
  busy.value = true
  failed.value = false
  status.value = ''
  const credentials = { email: email.value.trim(), password: password.value }
  try {
    const { data, error } = creating.value
      ? await props.client.auth.signUp({
          ...credentials,
          options: { emailRedirectTo: window.location.origin },
        })
      : await props.client.auth.signInWithPassword(credentials)
    if (error) throw error
    if (!data.session) status.value = 'Confira seu e-mail para confirmar a conta.'
  } catch (error) {
    failed.value = true
    if (error.code === 'email_not_confirmed') {
      status.value = 'Confirme seu e-mail antes de entrar.'
    } else if (error.code === 'invalid_credentials') {
      status.value = 'Confira o e-mail e a senha.'
    } else {
      status.value = 'Não foi possível concluir. Confira os dados e tente novamente.'
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <h1>{{ creating ? 'Crie sua conta' : 'Entre na sua conta' }}</h1>
  <p class="muted">Acompanhe as manchetes da BBC e converse sobre as notícias.</p>
  <form class="auth-form" @submit.prevent="submit">
    <label>
      E-mail
      <input v-model="email" type="email" autocomplete="email" required />
    </label>
    <label>
      Senha
      <input v-model="password" type="password" :minlength="creating ? 8 : undefined"
        :autocomplete="creating ? 'new-password' : 'current-password'" required />
    </label>
    <button class="primary-button" type="submit" :disabled="busy">
      {{ busy ? 'Aguarde…' : creating ? 'Criar conta' : 'Entrar' }}
    </button>
  </form>
  <p v-if="status" :class="failed ? 'notice error' : 'notice'" :role="failed ? 'alert' : 'status'">{{ status }}</p>
  <button class="text-button" type="button" :disabled="busy" @click="switchMode">
    {{ creating ? 'Já tenho conta' : 'Criar uma conta' }}
  </button>
</template>

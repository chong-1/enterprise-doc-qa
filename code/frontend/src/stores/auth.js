import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isAdmin = computed(() => user.value?.is_superuser ?? false)

  async function login(username, password) {
    const res = await api.post('/auth/login', { username, password })
    token.value = res.data.access_token
    localStorage.setItem('token', token.value)
    await fetchUser()
    return res
  }

  async function register(username, email, password) {
    const res = await api.post('/auth/register', { username, email, password })
    return res
  }

  async function fetchUser() {
    const res = await api.get('/users/me')
    user.value = res.data
    localStorage.setItem('user', JSON.stringify(user.value))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.href = '/login'
  }

  return { token, user, isAdmin, login, register, fetchUser, logout }
})

import { QueryClient, QueryObserver } from '@tanstack/query-core'
import { computed, onScopeDispose, shallowRef, watch, toValue, type MaybeRefOrGetter } from 'vue'
import { api } from '../services/api'
// Small Vue adapter over TanStack's framework-neutral query engine.
export const queryClient = new QueryClient({defaultOptions:{queries:{staleTime:30_000,retry:1,refetchOnWindowFocus:true}}})
queryClient.mount()
export function useApi<T>(path:MaybeRefOrGetter<string>) {
  const options = () => ({queryKey:[toValue(path)], queryFn:({signal}:{signal:AbortSignal})=>api<T>(toValue(path),{signal})})
  const observer = new QueryObserver<T>(queryClient, options())
  const state = shallowRef(observer.getCurrentResult())
  const unsubscribe = observer.subscribe(value=>state.value=value)
  watch(()=>toValue(path),()=>observer.setOptions(options()))
  onScopeDispose(()=>{unsubscribe();observer.destroy()})
  return {data:computed(()=>state.value.data), loading:computed(()=>state.value.isPending), error:computed(()=>state.value.error), refresh:()=>observer.refetch()}
}
export async function refreshData() { await queryClient.invalidateQueries() }

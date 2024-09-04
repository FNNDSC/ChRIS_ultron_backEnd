
from collections import deque


class EdgeNode:

    def __init__(self, vert):
        self.vert = vert  # int >= 1
        self.next = None

    def __repr__(self):
        return f'vertice: {self.vert}'


class Graph:

    def __init__(self, nvert, directed=False):
        length = nvert + 1  # values start at pos 1

        # array of EdgeNode linked lists
        self.edges = length * [None]
        # out degree of each vertex (adj list length)
        self.degrees = length * [0]
        self.nvert = nvert
        self.nedge = 0

        self.directed = directed

        # graph traverse params for both BFS and DFS
        self._processed = None
        self._discovered = None
        self._parent = None

        # additional graph traverse params for DFS
        self._finished = False
        self._entry_time = None
        self._exit_time = None
        self._time = 0
        self.cycle = []  # cycle path if a cycle is found during DFS

    def insert_edge(self, x, y):
        self._insert_edge(x, y)
        if not self.directed:
            self._insert_edge(y, x)
        self.nedge += 1

    def _insert_edge(self, x, y):
        en = EdgeNode(y)
        en.next = self.edges[x]
        self.edges[x] = en
        self.degrees[x] += 1

    def bfs(self, start_vert):
        self._initialize_search()
        queue = deque()

        self._discovered[start_vert] = True
        queue.append(start_vert)
        while queue:
            x = queue.popleft()
            self._bfs_process_vertex_early(x)
            en = self.edges[x]
            while en:
                y = en.vert
                # prevents proccesing same edge
                # twice in undirected graphs: (x,y)==(y,x)
                if not self._processed[y] or self.directed:
                    self._bfs_process_edge(x, y)
                if not self._discovered[y]:
                    self._discovered[y] = True
                    # queue of discovered but not
                    # processed yet
                    queue.append(y)
                    # BFS-tree
                    # (shortest paths in unweighted graphs)
                    self._parent[y] = x
                en = en.next
            self._processed[x] = True
            self._bfs_process_vertex_late(x)

    def _initialize_search(self):
        length = self.nvert + 1
        # parameters for both BFS and DFS
        self._processed = length * [False]
        self._discovered = length * [False]
        self._parent = length * [None]

        # additional parameters for DFS
        self._finished = False
        self._entry_time = length * [0]
        self._exit_time = length * [0]
        self._time = 0
        self.cycle = []  # cycle path if a cycle is found during DFS

    def dfs(self, start_vert):
        self._initialize_search()
        self._dfs(start_vert)

    def _dfs(self, v):
        if self._finished:
            return

        self._discovered[v] = True
        # descendants have higher entry time
        # and smaller exit time
        self._time += 1
        self._entry_time[v] = self._time
        self._dfs_process_vertex_early(v)

        en = self.edges[v]
        while en:
            y = en.vert
            if not self._discovered[y]:
                self._parent[y] = v  # DFS-tree
                self._dfs_process_edge1(v, y)  # tree edge
                self._dfs(y)
            elif not self._processed[y] or self.directed:
                # actual proc inside will only ocurr if
                # parent(v)!=y (i.e y is a higher
                # ancestor not mark as processed yet)
                self._dfs_process_edge2(v, y)  # non-tree edge
            if self._finished:
                return
            en = en.next

        self._dfs_process_vertex_late(v)
        self._time += 1
        self._exit_time[v] = self._time
        self._processed[v] = True

    def _bfs_process_vertex_early(self, x):
        pass

    def _bfs_process_vertex_late(self, x):
        pass

    def _bfs_process_edge(self, x, y):
        pass

    def _dfs_process_vertex_early(self, x):
        pass

    def _dfs_process_vertex_late(self, x):
        pass

    def _dfs_process_edge1(self, x, y):
        pass

    def _dfs_process_edge2(self, x, y):
        # find cycle
        if self.directed:
            if self._directed_graph_edge_clasification(x, y) == 'back':
                # directed cycle from {y} to {x}
                self.find_path(y, x)
                self.cycle.append(self.cycle[0])
                self._finished = True
        else:
            if self._parent[x] != y:
                # undirected cycle from {y} to {x}
                self.find_path(y, x)
                self.cycle.append(self.cycle[0])
                self._finished = True

    def _directed_graph_edge_clasification(self, x, y):
        if self._parent[y] == x:
            return 'tree'
        if self._discovered[y] and not self._processed[y]:
            return 'back'
        if self._processed[y] and (self._entry_time[y] > self._entry_time[x]):
            return 'forward'
        if self._processed[y] and (self._entry_time[y] < self._entry_time[x]):
            return 'cross'
        print(f"Warning: unclassified edge ({x},{y})\n")

    def find_path(self, start, end):
        if start == end or not end:
            self.cycle.append(start)
        else:
            self.find_path(start, self._parent[end])
            self.cycle.append(end)

    def connected_components(self):
        length = self.nvert + 1
        discovered = length * [False]
        c = 0
        for i in range(1, length):
            if not discovered[i]:
                c += 1
                print(f'Component {c}:')
                self.bfs(i)
                discovered = [discovered[j] or
                              self._discovered[j]
                              for j in range(length)]
                print('\n')


    def __repr__(self):
        rep = ''
        for i in range(1, self.nvert + 1):
            rep += f'{i}: --> '
            node = self.edges[i]
            while node:
                rep += f'{node.vert} --> '
                node = node.next
            rep += 'None\n'
        return rep

package com.maraffa.beccaccino.ui.navigation

sealed class Screen(val route: String) {
    object Home : Screen("home")

    object Lobby : Screen("lobby/{roomId}") {
        fun createRoute(roomId: String) = "lobby/$roomId"
    }

    object Game : Screen("game/{roomId}") {
        fun createRoute(roomId: String) = "game/$roomId"
    }

    object Result : Screen("result/{roomId}") {
        fun createRoute(roomId: String) = "result/$roomId"
    }
}

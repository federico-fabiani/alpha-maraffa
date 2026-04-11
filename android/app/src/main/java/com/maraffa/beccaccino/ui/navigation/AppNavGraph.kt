package com.maraffa.beccaccino.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.maraffa.beccaccino.ui.screen.game.GameScreen
import com.maraffa.beccaccino.ui.screen.home.HomeScreen
import com.maraffa.beccaccino.ui.screen.lobby.LobbyScreen
import com.maraffa.beccaccino.ui.screen.result.ResultScreen

@Composable
fun AppNavGraph(navController: NavHostController = rememberNavController()) {
    NavHost(navController = navController, startDestination = Screen.Home.route) {

        composable(Screen.Home.route) {
            HomeScreen(
                onNavigateToLobby = { roomId ->
                    navController.navigate(Screen.Lobby.createRoute(roomId))
                }
            )
        }

        composable(
            route = Screen.Lobby.route,
            arguments = listOf(navArgument("roomId") { type = NavType.StringType })
        ) {
            LobbyScreen(
                onGameStarted = { roomId ->
                    navController.navigate(Screen.Game.createRoute(roomId)) {
                        popUpTo(Screen.Home.route)
                    }
                },
                onBack = { navController.popBackStack() }
            )
        }

        composable(
            route = Screen.Game.route,
            arguments = listOf(navArgument("roomId") { type = NavType.StringType })
        ) {
            GameScreen(
                onGameOver = { roomId ->
                    navController.navigate(Screen.Result.createRoute(roomId)) {
                        popUpTo(Screen.Home.route)
                    }
                }
            )
        }

        composable(
            route = Screen.Result.route,
            arguments = listOf(navArgument("roomId") { type = NavType.StringType })
        ) {
            ResultScreen(
                onHome = {
                    navController.navigate(Screen.Home.route) {
                        popUpTo(0) { inclusive = true }
                    }
                }
            )
        }
    }
}
